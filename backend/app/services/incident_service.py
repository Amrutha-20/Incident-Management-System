"""
Incident service — orchestrates Work Item lifecycle operations.
All business logic lives here; routers call this, not repositories directly.
"""

from __future__ import annotations
from typing import Optional
import structlog

from app.core.state_machine import apply_transition, InvalidTransitionError, MissingRCAError
from app.db.postgres import WorkItemRepository
from app.db.mongo import SignalRepository
from app.db.cache import DashboardCache
from app.db.timeseries import TimeseriesRepository
from app.models.schemas import (
    WorkItem, WorkItemStatus, StatusTransitionRequest, RCARecord
)

logger = structlog.get_logger(__name__)


class IncidentService:
    def __init__(
        self,
        pg: WorkItemRepository,
        mongo: SignalRepository,
        cache: DashboardCache,
        tsdb: TimeseriesRepository,
    ) -> None:
        self._pg = pg
        self._mongo = mongo
        self._cache = cache
        self._tsdb = tsdb

    async def get_active_incidents(self, limit: int = 100) -> list[WorkItem]:
        # Try cache first (hot-path)
        cached = await self._cache.get_active_work_items()
        if cached is not None:
            return [WorkItem(**item) for item in cached]

        # Cache miss → query PostgreSQL and repopulate
        work_items = await self._pg.list_active(limit=limit)
        await self._cache.set_active_work_items(work_items)
        return work_items

    async def get_incident_detail(self, work_item_id: str) -> Optional[dict]:
        wi = await self._pg.get(work_item_id)
        if not wi:
            return None

        signals = await self._mongo.get_signals_for_work_item(work_item_id, limit=200)
        rca = await self._pg.get_rca(work_item_id)
        signal_count = await self._mongo.count_signals_for_work_item(work_item_id)

        return {
            "work_item": wi.model_dump(mode="json"),
            "signals": signals,
            "signal_count": signal_count,
            "rca": rca.model_dump(mode="json") if rca else None,
        }

    async def transition_status(
        self, work_item_id: str, request: StatusTransitionRequest
    ) -> WorkItem:
        wi = await self._pg.get(work_item_id)
        if not wi:
            raise ValueError(f"Work Item {work_item_id} not found")

        current_status = WorkItemStatus(wi.status) if isinstance(wi.status, str) else wi.status

        # State machine validates transition (raises on invalid)
        new_status, rca_record = apply_transition(
            current_status, request.new_status, request.rca
        )

        # Persist atomically
        updated = await self._pg.update_status_and_append_signal(
            work_item_id,
            new_status.value,
            None,
            rca_record,
        )

        # Write MTTR to InfluxDB if closing
        if new_status == WorkItemStatus.CLOSED and rca_record:
            import asyncio
            asyncio.create_task(
                self._tsdb.write_mttr(work_item_id, rca_record, wi.component_id)
            )

        # Invalidate caches
        await self._cache.invalidate()
        await self._cache.invalidate_work_item(work_item_id)

        logger.info(
            "incident.status_changed",
            work_item_id=work_item_id,
            from_status=current_status.value,
            to_status=new_status.value,
        )
        return updated