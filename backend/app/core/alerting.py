"""
Alerting Strategy (Strategy pattern).

Each component type has a different alerting strategy:
  - RDBMS      → P0 PagerDuty-style immediate alert
  - MCP_HOST   → P0 alert + escalation chain
  - API        → P1 alert with cooldown
  - ASYNC_QUEUE → P1 alert
  - CACHE      → P2 alert (degraded, not down)
  - NOSQL      → P2 alert

New strategies can be swapped in without touching the engine.
In production these would call real alerting backends (PagerDuty, OpsGenie, Slack).
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
import structlog

from app.models.schemas import ComponentType, Priority, WorkItem

logger = structlog.get_logger(__name__)


@dataclass
class AlertResult:
    sent: bool
    channel: str
    priority: Priority
    message: str


# ─────────────────────────────────────────────
# Abstract strategy
# ─────────────────────────────────────────────

class AlertingStrategy(ABC):
    @abstractmethod
    async def send_alert(self, work_item: WorkItem) -> AlertResult:
        ...


# ─────────────────────────────────────────────
# Concrete strategies
# ─────────────────────────────────────────────

class RDBMSAlertStrategy(AlertingStrategy):
    """P0 — database down is total outage. Page immediately."""

    async def send_alert(self, work_item: WorkItem) -> AlertResult:
        msg = (
            f"[P0-CRITICAL] RDBMS FAILURE on {work_item.component_id}. "
            f"WI: {work_item.work_item_id}. Immediate response required."
        )
        logger.critical("alert.rdbms_p0", work_item_id=work_item.work_item_id, msg=msg)
        # TODO: integrate PagerDuty / OpsGenie SDK here
        return AlertResult(sent=True, channel="pagerduty", priority=Priority.P0, message=msg)


class MCPHostAlertStrategy(AlertingStrategy):
    """P0 — MCP host failure cascades to all downstream agents."""

    async def send_alert(self, work_item: WorkItem) -> AlertResult:
        msg = (
            f"[P0-CRITICAL] MCP HOST DOWN: {work_item.component_id}. "
            f"All dependent agents may be affected. WI: {work_item.work_item_id}"
        )
        logger.critical("alert.mcp_p0", work_item_id=work_item.work_item_id, msg=msg)
        return AlertResult(sent=True, channel="pagerduty+slack", priority=Priority.P0, message=msg)


class APIAlertStrategy(AlertingStrategy):
    """P1 — API degradation, escalate if not resolved within SLA."""

    async def send_alert(self, work_item: WorkItem) -> AlertResult:
        msg = (
            f"[P1-HIGH] API Degradation on {work_item.component_id}. "
            f"WI: {work_item.work_item_id}. Monitor and escalate if >5min."
        )
        logger.error("alert.api_p1", work_item_id=work_item.work_item_id, msg=msg)
        return AlertResult(sent=True, channel="slack", priority=Priority.P1, message=msg)


class AsyncQueueAlertStrategy(AlertingStrategy):
    """P1 — queue backlog growing, downstream consumers impacted."""

    async def send_alert(self, work_item: WorkItem) -> AlertResult:
        msg = (
            f"[P1-HIGH] Async Queue issue on {work_item.component_id}. "
            f"Consumer lag may be growing. WI: {work_item.work_item_id}"
        )
        logger.error("alert.queue_p1", work_item_id=work_item.work_item_id, msg=msg)
        return AlertResult(sent=True, channel="slack", priority=Priority.P1, message=msg)


class CacheAlertStrategy(AlertingStrategy):
    """P2 — cache miss storm, degraded performance but not down."""

    async def send_alert(self, work_item: WorkItem) -> AlertResult:
        msg = (
            f"[P2-MEDIUM] Cache degradation on {work_item.component_id}. "
            f"Fallback to DB active. WI: {work_item.work_item_id}"
        )
        logger.warning("alert.cache_p2", work_item_id=work_item.work_item_id, msg=msg)
        return AlertResult(sent=True, channel="slack", priority=Priority.P2, message=msg)


class NoSQLAlertStrategy(AlertingStrategy):
    """P2 — NoSQL signal store degraded; signals may queue up."""

    async def send_alert(self, work_item: WorkItem) -> AlertResult:
        msg = (
            f"[P2-MEDIUM] NoSQL store issue on {work_item.component_id}. "
            f"Signal persistence may lag. WI: {work_item.work_item_id}"
        )
        logger.warning("alert.nosql_p2", work_item_id=work_item.work_item_id, msg=msg)
        return AlertResult(sent=True, channel="email", priority=Priority.P2, message=msg)


# ─────────────────────────────────────────────
# Strategy resolver
# ─────────────────────────────────────────────

_STRATEGY_MAP: dict[str, type[AlertingStrategy]] = {
    ComponentType.RDBMS: RDBMSAlertStrategy,
    ComponentType.MCP_HOST: MCPHostAlertStrategy,
    ComponentType.API: APIAlertStrategy,
    ComponentType.ASYNC_QUEUE: AsyncQueueAlertStrategy,
    ComponentType.CACHE: CacheAlertStrategy,
    ComponentType.NOSQL: NoSQLAlertStrategy,
}


def get_alert_strategy(component_type: str) -> AlertingStrategy:
    cls = _STRATEGY_MAP.get(component_type, CacheAlertStrategy)
    return cls()


async def dispatch_alert(work_item: WorkItem) -> AlertResult:
    strategy = get_alert_strategy(work_item.component_type)
    return await strategy.send_alert(work_item)
