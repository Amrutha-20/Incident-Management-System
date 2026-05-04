from __future__ import annotations
from enum import Enum
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, model_validator
import uuid


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class ComponentType(str, Enum):
    API = "API"
    MCP_HOST = "MCP_HOST"
    CACHE = "CACHE"
    ASYNC_QUEUE = "ASYNC_QUEUE"
    RDBMS = "RDBMS"
    NOSQL = "NOSQL"


class Priority(str, Enum):
    P0 = "P0"  # Critical
    P1 = "P1"  # High
    P2 = "P2"  # Medium
    P3 = "P3"  # Low


class WorkItemStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class RootCauseCategory(str, Enum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    CODE_BUG = "CODE_BUG"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    CONFIGURATION = "CONFIGURATION"
    CAPACITY = "CAPACITY"
    SECURITY = "SECURITY"
    UNKNOWN = "UNKNOWN"


# ─────────────────────────────────────────────
# Signal (raw inbound payload)
# ─────────────────────────────────────────────

class SignalPayload(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_id: str = Field(..., description="e.g. CACHE_CLUSTER_01")
    component_type: ComponentType
    error_code: str
    message: str
    severity: Priority
    metadata: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# RCA object
# ─────────────────────────────────────────────

class RCACreate(BaseModel):
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    root_cause_description: str = Field(..., min_length=20)
    fix_applied: str = Field(..., min_length=10)
    prevention_steps: str = Field(..., min_length=10)

    @model_validator(mode="after")
    def end_after_start(self) -> RCACreate:
        if self.incident_end <= self.incident_start:
            raise ValueError("incident_end must be after incident_start")
        return self


class RCARecord(RCACreate):
    rca_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mttr_seconds: float = 0.0
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def calculate_mttr(self) -> RCARecord:
        delta = (self.incident_end - self.incident_start).total_seconds()
        self.mttr_seconds = delta
        return self


# ─────────────────────────────────────────────
# Work Item
# ─────────────────────────────────────────────

class WorkItemCreate(BaseModel):
    component_id: str
    component_type: ComponentType
    priority: Priority
    title: str
    signal_ids: List[str] = Field(default_factory=list)


class WorkItem(WorkItemCreate):
    work_item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: WorkItemStatus = WorkItemStatus.OPEN
    rca: Optional[RCARecord] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    first_signal_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


# ─────────────────────────────────────────────
# State transition request
# ─────────────────────────────────────────────

class StatusTransitionRequest(BaseModel):
    new_status: WorkItemStatus
    rca: Optional[RCACreate] = None


# ─────────────────────────────────────────────
# API responses
# ─────────────────────────────────────────────

class SignalAck(BaseModel):
    signal_id: str
    work_item_id: Optional[str]
    debounced: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    signals_per_sec: float
    buffer_utilization_pct: float
    active_work_items: int
    uptime_seconds: float
    checks: dict[str, str]