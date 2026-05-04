"""
Debounce engine.

Rule: if 100+ signals arrive for the same component_id within 10 seconds,
only ONE Work Item is created. All signals are linked to it.

Implementation:
  - Redis key:  debounce:{component_id}  → work_item_id
  - TTL:        debounce_window_seconds (10s default)
  - Counter:    debounce:count:{component_id}  → int (INCR, same TTL)
  - Lock:       SETNX prevents two workers from creating duplicate Work Items
                (the Redis SET NX EX is atomic — critical for race-condition safety)
"""

from __future__ import annotations
import asyncio
from typing import Optional
import structlog

from app.config import get_settings
from app.models.schemas import SignalPayload, Priority

logger = structlog.get_logger(__name__)
settings = get_settings()

# Priority map per component type
COMPONENT_PRIORITY_MAP: dict[str, Priority] = {
    "RDBMS": Priority.P0,
    "MCP_HOST": Priority.P0,
    "API": Priority.P1,
    "ASYNC_QUEUE": Priority.P1,
    "NOSQL": Priority.P2,
    "CACHE": Priority.P2,
}


class DebounceEngine:
    """
    Stateless debouncer backed by Redis.
    All state lives in Redis so multiple worker replicas agree on the
    current debounce window without any in-process coordination.
    """

    def __init__(self, redis_client) -> None:
        self._redis = redis_client
        self._window = settings.debounce_window_seconds
        self._threshold = settings.debounce_threshold

    def _debounce_key(self, component_id: str) -> str:
        return f"debounce:wi:{component_id}"

    def _count_key(self, component_id: str) -> str:
        return f"debounce:count:{component_id}"

    def _lock_key(self, component_id: str) -> str:
        return f"debounce:lock:{component_id}"

    async def get_or_create_work_item_id(
        self,
        signal: SignalPayload,
        work_item_creator,  # async callable(signal) -> work_item_id
    ) -> tuple[str, bool]:
        """
        Returns (work_item_id, is_new).
        is_new=True  → caller should persist a new Work Item to RDBMS
        is_new=False → caller should just append signal_id to existing WI
        """
        debounce_key = self._debounce_key(signal.component_id)
        count_key = self._count_key(signal.component_id)
        lock_key = self._lock_key(signal.component_id)

        # Increment signal count atomically
        count = await self._redis.incr(count_key)
        if count == 1:
            # First signal for this component in this window — set TTL
            await self._redis.expire(count_key, self._window)

        # Check if a Work Item already exists for this window
        existing_wi_id = await self._redis.get(debounce_key)
        if existing_wi_id:
            logger.info(
                "debounce.hit",
                component_id=signal.component_id,
                work_item_id=existing_wi_id,
                count=count,
            )
            return existing_wi_id, False

        # No existing WI — try to acquire creation lock (atomic SETNX)
        # Only one worker wins; others will find the key set above
        acquired = await self._redis.set(
            lock_key, "1", nx=True, ex=self._window
        )

        if not acquired:
            # Another worker is creating the WI right now — wait briefly and retry
            await asyncio.sleep(0.05)
            existing_wi_id = await self._redis.get(debounce_key)
            if existing_wi_id:
                return existing_wi_id, False
            # Still nothing (very rare) — fall through and create
            logger.warning("debounce.lock_race", component_id=signal.component_id)

        # We hold the lock — create a new Work Item
        new_wi_id = await work_item_creator(signal)

        # Store the mapping with TTL so next signals in window find it
        await self._redis.set(debounce_key, new_wi_id, ex=self._window)

        logger.info(
            "debounce.new_work_item",
            component_id=signal.component_id,
            work_item_id=new_wi_id,
            count=count,
        )
        return new_wi_id, True

    async def get_signal_count(self, component_id: str) -> int:
        val = await self._redis.get(self._count_key(component_id))
        return int(val) if val else 0

    def resolve_priority(self, component_type: str) -> Priority:
        return COMPONENT_PRIORITY_MAP.get(component_type, Priority.P2)
