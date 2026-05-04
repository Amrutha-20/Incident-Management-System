"""
Async worker pool — drains the ring buffer and persists signals.

Each worker:
  1. Dequeues a signal from the ring buffer
  2. Calls the debounce engine to get/create a Work Item
  3. Stores the raw signal in MongoDB
  4. Updates the Work Item's signal list in PostgreSQL (atomic tx)
  5. Writes timeseries point to InfluxDB
  6. If new Work Item → dispatches alert + caches in Redis
  7. Logs throughput every N seconds (observability)

Retry logic: DB writes are retried up to 3 times with exponential backoff.
If all retries fail, the signal is logged as lost (never silently swallowed).
"""

from __future__ import annotations
import asyncio
import time
from datetime import datetime
import structlog

from app.config import get_settings
from app.core.ring_buffer import SignalRingBuffer
from app.core.debounce import DebounceEngine
from app.core.alerting import dispatch_alert
from app.db.postgres import WorkItemRepository
from app.db.mongo import SignalRepository
from app.db.cache import DashboardCache
from app.db.timeseries import TimeseriesRepository
from app.models.schemas import SignalPayload, WorkItem, WorkItemCreate, Priority

logger = structlog.get_logger(__name__)
settings = get_settings()


async def _retry(coro_fn, retries: int = 3, base_delay: float = 0.1):
    """Retry an async callable with exponential backoff."""
    last_exc = None
    for attempt in range(retries):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            delay = base_delay * (2 ** attempt)
            logger.warning("worker.retry", attempt=attempt + 1, delay=delay, error=str(exc))
            await asyncio.sleep(delay)
    raise last_exc


class SignalWorker:
    def __init__(
        self,
        worker_id: int,
        buffer: SignalRingBuffer,
        debounce: DebounceEngine,
        pg_repo: WorkItemRepository,
        mongo_repo: SignalRepository,
        cache: DashboardCache,
        tsdb: TimeseriesRepository,
    ) -> None:
        self._id = worker_id
        self._buffer = buffer
        self._debounce = debounce
        self._pg = pg_repo
        self._mongo = mongo_repo
        self._cache = cache
        self._tsdb = tsdb
        self._running = False
        self._processed = 0

    async def _create_work_item(self, signal: SignalPayload) -> str:
        priority = self._debounce.resolve_priority(
            signal.component_type if isinstance(signal.component_type, str) else signal.component_type.value
        )
        wi = WorkItem(
            component_id=signal.component_id,
            component_type=signal.component_type,
            priority=priority,
            title=f"{signal.component_type} failure on {signal.component_id}",
            signal_ids=[signal.signal_id],
            first_signal_at=signal.received_at,
        )
        await _retry(lambda: self._pg.create(wi))
        return wi.work_item_id

    async def _process_signal(self, signal: SignalPayload) -> None:
        # ── Debounce: get or create Work Item ──
        wi_id, is_new = await self._debounce.get_or_create_work_item_id(
            signal, self._create_work_item
        )

        # ── Persist raw signal to MongoDB (audit log) ──
        await _retry(lambda: self._mongo.insert(signal, wi_id))

        # ── Append signal to Work Item in PostgreSQL ──
        if not is_new:
            await _retry(
                lambda: self._pg.update_status_and_append_signal(
                    wi_id, None, signal.signal_id
                )
            )

        # ── Timeseries point ──
        asyncio.create_task(self._tsdb.write_signal(signal, wi_id))

        # ── On new Work Item: alert + cache ──
        if is_new:
            wi = await self._pg.get(wi_id)
            if wi:
                asyncio.create_task(dispatch_alert(wi))
                asyncio.create_task(self._cache.set_work_item(wi))
                asyncio.create_task(self._cache.invalidate())

        self._processed += 1
        logger.debug(
            "worker.signal_processed",
            worker_id=self._id,
            signal_id=signal.signal_id,
            work_item_id=wi_id,
            is_new=is_new,
        )

    async def run(self) -> None:
        self._running = True
        logger.info("worker.started", worker_id=self._id)
        while self._running:
            signal = await self._buffer.dequeue(timeout=1.0)
            if signal is None:
                continue
            try:
                await self._process_signal(signal)
            except Exception as exc:
                logger.error(
                    "worker.signal_failed",
                    worker_id=self._id,
                    signal_id=getattr(signal, "signal_id", "unknown"),
                    error=str(exc),
                )

    def stop(self) -> None:
        self._running = False

    @property
    def processed_count(self) -> int:
        return self._processed


class WorkerPool:
    """Manages N concurrent SignalWorker tasks."""

    def __init__(
        self,
        buffer: SignalRingBuffer,
        debounce: DebounceEngine,
        pg_repo: WorkItemRepository,
        mongo_repo: SignalRepository,
        cache: DashboardCache,
        tsdb: TimeseriesRepository,
        worker_count: int = 4,
    ) -> None:
        self._workers = [
            SignalWorker(i, buffer, debounce, pg_repo, mongo_repo, cache, tsdb)
            for i in range(worker_count)
        ]
        self._tasks: list[asyncio.Task] = []
        self._buffer = buffer
        self._tsdb = tsdb
        self._obs_task: asyncio.Task | None = None

    async def start(self) -> None:
        for worker in self._workers:
            self._tasks.append(asyncio.create_task(worker.run()))
        self._obs_task = asyncio.create_task(self._observability_loop())
        logger.info("worker_pool.started", count=len(self._workers))

    async def stop(self) -> None:
        for worker in self._workers:
            worker.stop()
        if self._obs_task:
            self._obs_task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("worker_pool.stopped")

    async def _observability_loop(self) -> None:
        """Print throughput metrics every N seconds (assignment requirement)."""
        interval = settings.throughput_report_interval
        while True:
            await asyncio.sleep(interval)
            tps = self._buffer.stats.throughput_per_sec(window=interval)
            total_enqueued = self._buffer.stats.total_enqueued
            total_dropped = self._buffer.stats.total_dropped
            buf_util = self._buffer.utilization_pct
            total_processed = sum(w.processed_count for w in self._workers)

            print(
                f"[THROUGHPUT] signals/sec={tps:.1f} | "
                f"enqueued={total_enqueued} | dropped={total_dropped} | "
                f"processed={total_processed} | buffer={buf_util:.1f}%",
                flush=True,
            )
            logger.info(
                "observability.throughput",
                signals_per_sec=round(tps, 2),
                total_enqueued=total_enqueued,
                total_dropped=total_dropped,
                buffer_utilization_pct=round(buf_util, 2),
            )
            asyncio.create_task(self._tsdb.write_throughput(tps))
