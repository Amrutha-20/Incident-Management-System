"""
Ring buffer for high-throughput signal ingestion.

Guarantees:
- Lock-free reads of current size (atomic int via asyncio)
- Never crashes if downstream persistence is slow
- Signals dropped (not queued forever) when at capacity → backpressure signal
- O(1) enqueue and dequeue
"""

from __future__ import annotations
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
import structlog

from app.models.schemas import SignalPayload

logger = structlog.get_logger(__name__)


@dataclass
class RingBufferStats:
    total_enqueued: int = 0
    total_dropped: int = 0
    total_dequeued: int = 0
    enqueue_timestamps: deque = field(default_factory=lambda: deque(maxlen=10_000))

    def throughput_per_sec(self, window: float = 5.0) -> float:
        now = time.monotonic()
        cutoff = now - window
        recent = sum(1 for t in self.enqueue_timestamps if t >= cutoff)
        return recent / window


class SignalRingBuffer:
    """
    Bounded async-safe circular buffer.
    Producers call enqueue(); consumers call dequeue() or drain().
    When full, new signals are dropped and counted — never block the HTTP layer.
    """

    def __init__(self, capacity: int = 50_000) -> None:
        self._capacity = capacity
        self._buffer: deque[SignalPayload] = deque()
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()
        self.stats = RingBufferStats()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def size(self) -> int:
        return len(self._buffer)

    @property
    def utilization_pct(self) -> float:
        return (self.size / self._capacity) * 100

    @property
    def is_full(self) -> bool:
        return len(self._buffer) >= self._capacity

    async def enqueue(self, signal: SignalPayload) -> bool:
        """
        Add a signal. Returns True if accepted, False if dropped.
        Never raises; never blocks the caller.
        """
        async with self._lock:
            if len(self._buffer) >= self._capacity:
                self.stats.total_dropped += 1
                logger.warning(
                    "ring_buffer.drop",
                    signal_id=signal.signal_id,
                    component_id=signal.component_id,
                    buffer_size=len(self._buffer),
                )
                return False

            self._buffer.append(signal)
            self.stats.total_enqueued += 1
            self.stats.enqueue_timestamps.append(time.monotonic())
            self._not_empty.set()
            return True

    async def dequeue(self, timeout: float = 1.0) -> Optional[SignalPayload]:
        """
        Pop one signal. Waits up to `timeout` seconds.
        Returns None on timeout (lets worker loop check shutdown flag).
        """
        try:
            await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

        async with self._lock:
            if not self._buffer:
                self._not_empty.clear()
                return None

            signal = self._buffer.popleft()
            self.stats.total_dequeued += 1
            if not self._buffer:
                self._not_empty.clear()
            return signal

    async def drain(self, batch_size: int = 100) -> list[SignalPayload]:
        """
        Drain up to `batch_size` signals atomically.
        Used by batch workers.
        """
        async with self._lock:
            batch = []
            for _ in range(min(batch_size, len(self._buffer))):
                batch.append(self._buffer.popleft())
                self.stats.total_dequeued += 1
            if not self._buffer:
                self._not_empty.clear()
            return batch
