"""
PostgreSQL repository — Work Items and RCA records.
All mutations are wrapped in explicit transactions.
Uses asyncpg directly (no ORM) for max throughput and explicit control.
"""

from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
import asyncpg
import structlog

from app.models.schemas import WorkItem, WorkItemStatus, RCARecord, Priority

logger = structlog.get_logger(__name__)

# DDL — run on startup
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS work_items (
    work_item_id   TEXT PRIMARY KEY,
    component_id   TEXT NOT NULL,
    component_type TEXT NOT NULL,
    priority       TEXT NOT NULL,
    title          TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'OPEN',
    signal_ids     JSONB NOT NULL DEFAULT '[]',
    first_signal_at TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rca_records (
    rca_id                  TEXT PRIMARY KEY,
    work_item_id            TEXT NOT NULL REFERENCES work_items(work_item_id),
    incident_start          TIMESTAMPTZ NOT NULL,
    incident_end            TIMESTAMPTZ NOT NULL,
    root_cause_category     TEXT NOT NULL,
    root_cause_description  TEXT NOT NULL,
    fix_applied             TEXT NOT NULL,
    prevention_steps        TEXT NOT NULL,
    mttr_seconds            DOUBLE PRECISION NOT NULL,
    submitted_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wi_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_wi_component ON work_items(component_id);
CREATE INDEX IF NOT EXISTS idx_wi_priority ON work_items(priority);
CREATE INDEX IF NOT EXISTS idx_rca_wi ON rca_records(work_item_id);
"""


class WorkItemRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def migrate(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)
        logger.info("db.migrated")

    async def create(self, work_item: WorkItem) -> WorkItem:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO work_items
                        (work_item_id, component_id, component_type, priority,
                         title, status, signal_ids, first_signal_at, created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT (work_item_id) DO NOTHING
                    """,
                    work_item.work_item_id,
                    work_item.component_id,
                    work_item.component_type if isinstance(work_item.component_type, str) else work_item.component_type.value,
                    work_item.priority if isinstance(work_item.priority, str) else work_item.priority.value,
                    work_item.title,
                    work_item.status if isinstance(work_item.status, str) else work_item.status.value,
                    json.dumps(work_item.signal_ids),
                    work_item.first_signal_at,
                    work_item.created_at,
                    work_item.updated_at,
                )
        logger.info("db.work_item.created", work_item_id=work_item.work_item_id)
        return work_item

    async def get(self, work_item_id: str) -> Optional[WorkItem]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM work_items WHERE work_item_id = $1", work_item_id
            )
        if not row:
            return None
        return self._row_to_model(dict(row))

    async def list_active(
        self, limit: int = 100, offset: int = 0
    ) -> list[WorkItem]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM work_items
                WHERE status != 'CLOSED'
                ORDER BY
                    CASE priority
                        WHEN 'P0' THEN 1 WHEN 'P1' THEN 2
                        WHEN 'P2' THEN 3 ELSE 4
                    END,
                    created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
        return [self._row_to_model(dict(r)) for r in rows]

    async def count_active(self) -> int:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM work_items WHERE status != 'CLOSED'"
            )

    async def update_status_and_append_signal(
        self,
        work_item_id: str,
        new_status: Optional[str],
        signal_id: Optional[str],
        rca: Optional[RCARecord] = None,
    ) -> Optional[WorkItem]:
        """
        Atomic transaction:
        1. Update status (if provided)
        2. Append signal_id to signal_ids array (if provided)
        3. Insert RCA record (if provided)
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if signal_id:
                    await conn.execute(
                        """
                        UPDATE work_items
                        SET signal_ids = signal_ids || $2::jsonb,
                            updated_at = now()
                        WHERE work_item_id = $1
                        """,
                        work_item_id,
                        json.dumps([signal_id]),
                    )

                if new_status:
                    await conn.execute(
                        """
                        UPDATE work_items
                        SET status = $2, updated_at = now()
                        WHERE work_item_id = $1
                        """,
                        work_item_id,
                        new_status,
                    )

                if rca:
                    await conn.execute(
                        """
                        INSERT INTO rca_records
                            (rca_id, work_item_id, incident_start, incident_end,
                             root_cause_category, root_cause_description,
                             fix_applied, prevention_steps, mttr_seconds, submitted_at)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        """,
                        rca.rca_id,
                        work_item_id,
                        rca.incident_start,
                        rca.incident_end,
                        rca.root_cause_category if isinstance(rca.root_cause_category, str) else rca.root_cause_category.value,
                        rca.root_cause_description,
                        rca.fix_applied,
                        rca.prevention_steps,
                        rca.mttr_seconds,
                        rca.submitted_at,
                    )

                row = await conn.fetchrow(
                    "SELECT * FROM work_items WHERE work_item_id = $1", work_item_id
                )

        return self._row_to_model(dict(row)) if row else None

    async def get_rca(self, work_item_id: str) -> Optional[RCARecord]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM rca_records WHERE work_item_id = $1", work_item_id
            )
        if not row:
            return None
        d = dict(row)
        return RCARecord(
            rca_id=d["rca_id"],
            incident_start=d["incident_start"],
            incident_end=d["incident_end"],
            root_cause_category=d["root_cause_category"],
            root_cause_description=d["root_cause_description"],
            fix_applied=d["fix_applied"],
            prevention_steps=d["prevention_steps"],
            mttr_seconds=d["mttr_seconds"],
            submitted_at=d["submitted_at"],
        )

    def _row_to_model(self, row: dict) -> WorkItem:
        signal_ids = row.get("signal_ids")
        if isinstance(signal_ids, str):
            signal_ids = json.loads(signal_ids)
        elif signal_ids is None:
            signal_ids = []

        return WorkItem(
            work_item_id=row["work_item_id"],
            component_id=row["component_id"],
            component_type=row["component_type"],
            priority=row["priority"],
            title=row["title"],
            status=WorkItemStatus(row["status"]),
            signal_ids=signal_ids,
            first_signal_at=row.get("first_signal_at"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )