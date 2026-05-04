from __future__ import annotations
from datetime import datetime, timezone
import structlog

from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from influxdb_client import Point

from app.config import get_settings
from app.models.schemas import SignalPayload, RCARecord

logger = structlog.get_logger(__name__)
settings = get_settings()

PRECISION = "s"


class TimeseriesRepository:
    def __init__(self) -> None:
        self._client = InfluxDBClientAsync(
            url=settings.influx_url,
            token=settings.influx_token,
            org=settings.influx_org,
        )
        self._write_api = self._client.write_api()

    async def write_signal(self, signal: SignalPayload, work_item_id: str) -> None:
        point = (
            Point("signal_ingested")
            .tag("component_id", signal.component_id)
            .tag("component_type", signal.component_type if isinstance(signal.component_type, str) else signal.component_type.value)
            .tag("severity", signal.severity if isinstance(signal.severity, str) else signal.severity.value)
            .tag("work_item_id", work_item_id)
            .field("count", 1)
            .time(signal.received_at, PRECISION)
        )
        try:
            await self._write_api.write(
                bucket=settings.influx_bucket,
                org=settings.influx_org,
                record=point,
            )
        except Exception as e:
            logger.warning("influx.write_signal.failed", error=str(e))

    async def write_mttr(self, work_item_id: str, rca: RCARecord, component_id: str) -> None:
        point = (
            Point("mttr")
            .tag("work_item_id", work_item_id)
            .tag("component_id", component_id)
            .tag("root_cause", rca.root_cause_category if isinstance(rca.root_cause_category, str) else rca.root_cause_category.value)
            .field("mttr_seconds", rca.mttr_seconds)
            .time(rca.submitted_at, PRECISION)
        )
        try:
            await self._write_api.write(
                bucket=settings.influx_bucket,
                org=settings.influx_org,
                record=point,
            )
            logger.info("influx.mttr_written", work_item_id=work_item_id, mttr=rca.mttr_seconds)
        except Exception as e:
            logger.warning("influx.write_mttr.failed", error=str(e))

    async def write_throughput(self, signals_per_sec: float) -> None:
        point = (
            Point("throughput")
            .field("signals_per_sec", signals_per_sec)
            .time(datetime.now(timezone.utc), PRECISION)
        )
        try:
            await self._write_api.write(
                bucket=settings.influx_bucket,
                org=settings.influx_org,
                record=point,
            )
        except Exception:
            pass

    async def close(self) -> None:
        await self._client.close()