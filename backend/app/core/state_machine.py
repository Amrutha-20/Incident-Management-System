"""
Work Item state machine (State pattern).

Valid transitions:
  OPEN → INVESTIGATING
  INVESTIGATING → RESOLVED
  RESOLVED → CLOSED  (only if RCA is complete and valid)
  RESOLVED → INVESTIGATING  (reopen)

Any other transition raises InvalidTransitionError.
The CLOSED gate is the critical business rule — RCA must be present and valid.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
import structlog

from app.models.schemas import WorkItemStatus, RCACreate, RCARecord

logger = structlog.get_logger(__name__)


class InvalidTransitionError(Exception):
    """Raised when a status transition is not permitted."""
    pass


class MissingRCAError(Exception):
    """Raised when attempting to CLOSE without a valid RCA."""
    pass


# ─────────────────────────────────────────────
# Abstract state
# ─────────────────────────────────────────────

class WorkItemState(ABC):
    @property
    @abstractmethod
    def status(self) -> WorkItemStatus:
        ...

    @abstractmethod
    def transition_to(
        self,
        new_status: WorkItemStatus,
        rca: Optional[RCACreate] = None,
    ) -> tuple[WorkItemStatus, Optional[RCARecord]]:
        """
        Returns (new_status, rca_record_or_None).
        Raises InvalidTransitionError or MissingRCAError on bad transitions.
        """
        ...

    def _reject(self, target: WorkItemStatus) -> None:
        raise InvalidTransitionError(
            f"Cannot transition from {self.status.value} to {target.value}"
        )


# ─────────────────────────────────────────────
# Concrete states
# ─────────────────────────────────────────────

class OpenState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.OPEN

    def transition_to(self, new_status, rca=None):
        if new_status == WorkItemStatus.INVESTIGATING:
            logger.info("state_machine.transition", from_=self.status, to=new_status)
            return WorkItemStatus.INVESTIGATING, None
        self._reject(new_status)


class InvestigatingState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.INVESTIGATING

    def transition_to(self, new_status, rca=None):
        if new_status == WorkItemStatus.RESOLVED:
            logger.info("state_machine.transition", from_=self.status, to=new_status)
            return WorkItemStatus.RESOLVED, None
        self._reject(new_status)


class ResolvedState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.RESOLVED

    def transition_to(self, new_status, rca=None):
        if new_status == WorkItemStatus.INVESTIGATING:
            # Allow reopen
            logger.info("state_machine.reopen", from_=self.status)
            return WorkItemStatus.INVESTIGATING, None

        if new_status == WorkItemStatus.CLOSED:
            # ── Critical gate: RCA must be complete ──
            if rca is None:
                raise MissingRCAError(
                    "RCA is required before closing a Work Item. "
                    "Provide a complete RCA object with root_cause_description, "
                    "fix_applied, and prevention_steps."
                )
            # Validate by constructing the record (pydantic raises on bad data)
            rca_record = RCARecord(
                **rca.model_dump(),
                mttr_seconds=(rca.incident_end - rca.incident_start).total_seconds(),
            )
            logger.info(
                "state_machine.close_with_rca",
                mttr_seconds=rca_record.mttr_seconds,
                category=rca_record.root_cause_category,
            )
            return WorkItemStatus.CLOSED, rca_record

        self._reject(new_status)


class ClosedState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.CLOSED

    def transition_to(self, new_status, rca=None):
        # Terminal state — nothing can transition out
        self._reject(new_status)


# ─────────────────────────────────────────────
# State factory
# ─────────────────────────────────────────────

_STATE_MAP: dict[WorkItemStatus, type[WorkItemState]] = {
    WorkItemStatus.OPEN: OpenState,
    WorkItemStatus.INVESTIGATING: InvestigatingState,
    WorkItemStatus.RESOLVED: ResolvedState,
    WorkItemStatus.CLOSED: ClosedState,
}


def get_state(status: WorkItemStatus) -> WorkItemState:
    cls = _STATE_MAP.get(status)
    if cls is None:
        raise ValueError(f"Unknown status: {status}")
    return cls()


def apply_transition(
    current_status: WorkItemStatus,
    new_status: WorkItemStatus,
    rca: Optional[RCACreate] = None,
) -> tuple[WorkItemStatus, Optional[RCARecord]]:
    """
    Top-level helper used by the service layer.
    Raises InvalidTransitionError or MissingRCAError on failure.
    """
    state = get_state(current_status)
    return state.transition_to(new_status, rca)
