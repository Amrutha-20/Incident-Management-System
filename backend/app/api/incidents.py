"""
Work Item (incident) endpoints.

GET    /api/v1/incidents          — list active incidents (cached hot-path)
GET    /api/v1/incidents/{id}     — incident detail with signals + RCA
PATCH  /api/v1/incidents/{id}/status — state machine transition
"""

from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, status
import structlog

from app.core.state_machine import InvalidTransitionError, MissingRCAError
from app.models.schemas import StatusTransitionRequest, WorkItem

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


def _get_service(request: Request):
    return request.app.state.incident_service


@router.get("", response_model=list[dict])
async def list_incidents(request: Request, limit: int = 100):
    """
    List active Work Items sorted by severity.
    Served from Redis cache when available; falls back to PostgreSQL.
    """
    svc = _get_service(request)
    incidents = await svc.get_active_incidents(limit=limit)
    return [i.model_dump(mode="json") for i in incidents]


@router.get("/{work_item_id}")
async def get_incident(work_item_id: str, request: Request):
    """
    Full incident detail including raw signals from MongoDB and RCA record.
    """
    svc = _get_service(request)
    detail = await svc.get_incident_detail(work_item_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work Item {work_item_id} not found",
        )
    return detail


@router.patch("/{work_item_id}/status")
async def transition_status(
    work_item_id: str,
    request_body: StatusTransitionRequest,
    request: Request,
):
    """
    Transition a Work Item through the state machine.

    Rules enforced server-side:
      - OPEN → INVESTIGATING → RESOLVED → CLOSED
      - RESOLVED → INVESTIGATING (reopen allowed)
      - CLOSED is terminal
      - RESOLVED → CLOSED requires a complete RCA object
    """
    svc = _get_service(request)
    try:
        updated = await svc.transition_status(work_item_id, request_body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MissingRCAError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    return updated.model_dump(mode="json")