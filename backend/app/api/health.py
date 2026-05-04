"""
/health endpoint — liveness + readiness + throughput metrics.
Returns 200 if the system is operational, 503 if any critical dependency is down.
"""

from __future__ import annotations
import time
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
import structlog

from app.models.schemas import HealthResponse

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["observability"])

_start_time = time.monotonic()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    app = request.app
    checks: dict[str, str] = {}
    all_ok = True

    # PostgreSQL check
    try:
        async with app.state.pg_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"
        all_ok = False

    # MongoDB check
    try:
        await app.state.mongo_client.admin.command("ping")
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"error: {e}"
        all_ok = False

    # Redis check
    try:
        await app.state.redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        all_ok = False

    # Ring buffer
    buffer = app.state.buffer
    checks["ring_buffer"] = (
        f"ok ({buffer.size}/{buffer.capacity} used, {buffer.utilization_pct:.1f}%)"
    )
    if buffer.utilization_pct > 90:
        checks["ring_buffer"] = f"warning: {buffer.utilization_pct:.1f}% full"

    tps = buffer.stats.throughput_per_sec(window=5)

    pg_repo = app.state.pg_repo
    try:
        active_count = await pg_repo.count_active()
    except Exception:
        active_count = -1

    uptime = time.monotonic() - _start_time
    resp_status = "ok" if all_ok else "degraded"

    payload = HealthResponse(
        status=resp_status,
        signals_per_sec=round(tps, 2),
        buffer_utilization_pct=round(buffer.utilization_pct, 2),
        active_work_items=active_count,
        uptime_seconds=round(uptime, 1),
        checks=checks,
    )

    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=payload.model_dump(), status_code=http_status)