"""
MongoDB repository — raw signal audit log.
Every single signal payload is stored here, regardless of debouncing.
Indexed on component_id and work_item_id for fast lookup from the UI.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Any
import structlog

from app.models.schemas import SignalPayload

logger = structlog.get_logger(__name__)

COLLECTION = "signals"


class SignalRepository:
    def __init__(self, client: Any, db_name: str) -> None:
        self._db = client[db_name]

    async def ensure_indexes(self) -> None:
        col = self._db[COLLECTION]
        await col.create_index("component_id")
        await col.create_index("work_item_id")
        await col.create_index("received_at")
        await col.create_index("signal_id", unique=True)
        logger.info("mongo.indexes_created")

    async def insert(self, signal: SignalPayload, work_item_id: str) -> None:
        doc = signal.model_dump(mode="json")
        doc["work_item_id"] = work_item_id
        col = self._db[COLLECTION]
        try:
            await col.insert_one(doc)
        except Exception as e:
            if "duplicate key" in str(e).lower() or "E11000" in str(e):
                logger.debug("mongo.duplicate_signal", signal_id=signal.signal_id)
            else:
                raise

    async def get_signals_for_work_item(
        self, work_item_id: str, limit: int = 500
    ) -> list[dict]:
        col = self._db[COLLECTION]
        cursor = col.find(
            {"work_item_id": work_item_id},
            {"_id": 0},
            sort=[("received_at", -1)],
            limit=limit,
        )
        return await cursor.to_list(length=limit)

    async def get_signals_for_component(
        self,
        component_id: str,
        since: Optional[datetime] = None,
        limit: int = 200,
    ) -> list[dict]:
        col = self._db[COLLECTION]
        query: dict = {"component_id": component_id}
        if since:
            query["received_at"] = {"$gte": since.isoformat()}
        cursor = col.find(query, {"_id": 0}, sort=[("received_at", -1)], limit=limit)
        return await cursor.to_list(length=limit)

    async def count_signals_for_work_item(self, work_item_id: str) -> int:
        col = self._db[COLLECTION]
        return await col.count_documents({"work_item_id": work_item_id})