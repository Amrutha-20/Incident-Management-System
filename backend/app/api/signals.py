"""
Signal ingestion endpoints.
POST /api/v1/signals — ingest a single signal
POST /api/v1/signals/batch — ingest up to 500 signals in one call
GET  /api/v1/signals/{work_item_id} — raw signals for a Work Item (from MongoDB)
"""

from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, status
import structlog

from app.models.schemas import SignalPayload, SignalAck

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/signals", tags=["signals"])


def _get_buffer(request: Request):
    return request.app.state.buffer


@router.post("", response_model=SignalAck, status_code=status.HTTP_202_ACCEPTED)
async def ingest_signal(signal: SignalPayload, request: Request):
    """
    Ingest a single signal. Always returns 202 — the signal is accepted
    into the ring buffer and processed asynchronously. If the buffer is full
    the signal is dropped and the response indicates it.
    """
    buffer = _get_buffer(request)
    accepted = await buffer.enqueue(signal)

    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Buffer at capacity. Retry with backoff.",
        )

    return SignalAck(
        signal_id=signal.signal_id,
        work_item_id=None,  # Unknown at ingest time (async processing)
        debounced=False,
        message="Signal accepted for async processing",
    )


@router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(signals: list[SignalPayload], request: Request):
    """
    Ingest up to 500 signals in one HTTP call.
    Useful for high-volume producers that want to reduce connection overhead.
    """
    if len(signals) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch size exceeds maximum of 500 signals",
        )

    buffer = _get_buffer(request)
    accepted = 0
    dropped = 0

    for signal in signals:
        ok = await buffer.enqueue(signal)
        if ok:
            accepted += 1
        else:
            dropped += 1

    return {
        "accepted": accepted,
        "dropped": dropped,
        "total": len(signals),
        "message": f"Accepted {accepted}/{len(signals)} signals",
    }


@router.get("/{work_item_id}")
async def get_signals(work_item_id: str, request: Request, limit: int = 200):
    """Retrieve raw signals from MongoDB for a given Work Item."""
    mongo_repo = request.app.state.mongo_repo
    signals = await mongo_repo.get_signals_for_work_item(work_item_id, limit=limit)
    return {"work_item_id": work_item_id, "signals": signals, "count": len(signals)}