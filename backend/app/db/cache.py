"""
Redis cache — dashboard hot-path.
Keeps the latest Work Item summaries in Redis so the UI never hits
PostgreSQL on every refresh. Invalidated on every status change.
"""

from __future__ import annotations
import json
from typing import Optional
import structlog

from app.models.schemas import WorkItem

logger = structlog.get_logger(__name__)

DASHBOARD_KEY = "dashboard:active_work_items"
DASHBOARD_TTL = 30  # seconds


class DashboardCache:
    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def set_active_work_items(self, work_items: list[WorkItem]) -> None:
        payload = json.dumps(
            [wi.model_dump(mode="json") for wi in work_items]
        )
        await self._redis.setex(DASHBOARD_KEY, DASHBOARD_TTL, payload)
        logger.debug("cache.dashboard.set", count=len(work_items))

    async def get_active_work_items(self) -> Optional[list[dict]]:
        raw = await self._redis.get(DASHBOARD_KEY)
        if raw is None:
            return None
        logger.debug("cache.dashboard.hit")
        return json.loads(raw)

    async def invalidate(self) -> None:
        await self._redis.delete(DASHBOARD_KEY)
        logger.debug("cache.dashboard.invalidated")

    async def set_work_item(self, work_item: WorkItem) -> None:
        key = f"wi:{work_item.work_item_id}"
        payload = json.dumps(work_item.model_dump(mode="json"))
        await self._redis.setex(key, 300, payload)

    async def get_work_item(self, work_item_id: str) -> Optional[dict]:
        raw = await self._redis.get(f"wi:{work_item_id}")
        return json.loads(raw) if raw else None

    async def invalidate_work_item(self, work_item_id: str) -> None:
        await self._redis.delete(f"wi:{work_item_id}")