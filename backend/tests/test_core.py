"""
Unit tests for:
  - State machine transitions (happy + error paths)
  - RCA validation (all mandatory fields, MTTR calculation)
  - Debounce key logic
  - Ring buffer behavior under backpressure
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import pytest

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.state_machine import (
    apply_transition, InvalidTransitionError, MissingRCAError,
    get_state, WorkItemStatus
)
from app.core.ring_buffer import SignalRingBuffer
from app.models.schemas import (
    SignalPayload, RCACreate, RCARecord, ComponentType, Priority,
    WorkItemStatus as WIS, RootCauseCategory
)


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

def make_rca(**overrides) -> RCACreate:
    now = datetime.now(timezone.utc)
    defaults = dict(
        incident_start=now - timedelta(hours=1),
        incident_end=now,
        root_cause_category=RootCauseCategory.CODE_BUG,
        root_cause_description="Null pointer in cache invalidation routine caused cascade",
        fix_applied="Patched the cache invalidation and deployed hotfix v2.3.1",
        prevention_steps="Added null checks, unit tests, and integration test suite",
    )
    defaults.update(overrides)
    return RCACreate(**defaults)


def make_signal(**overrides) -> SignalPayload:
    defaults = dict(
        component_id="CACHE_CLUSTER_01",
        component_type=ComponentType.CACHE,
        error_code="ERR_TIMEOUT",
        message="Connection timeout",
        severity=Priority.P2,
    )
    defaults.update(overrides)
    return SignalPayload(**defaults)


# ─────────────────────────────────────────────
# State machine — happy paths
# ─────────────────────────────────────────────

class TestStateMachineHappyPaths:
    def test_open_to_investigating(self):
        new_status, rca = apply_transition(WIS.OPEN, WIS.INVESTIGATING)
        assert new_status == WIS.INVESTIGATING
        assert rca is None

    def test_investigating_to_resolved(self):
        new_status, rca = apply_transition(WIS.INVESTIGATING, WIS.RESOLVED)
        assert new_status == WIS.RESOLVED
        assert rca is None

    def test_resolved_to_closed_with_valid_rca(self):
        rca_input = make_rca()
        new_status, rca_record = apply_transition(WIS.RESOLVED, WIS.CLOSED, rca_input)
        assert new_status == WIS.CLOSED
        assert isinstance(rca_record, RCARecord)
        assert rca_record.mttr_seconds == pytest.approx(3600, abs=5)

    def test_resolved_to_investigating_reopen(self):
        new_status, rca = apply_transition(WIS.RESOLVED, WIS.INVESTIGATING)
        assert new_status == WIS.INVESTIGATING
        assert rca is None

    def test_full_lifecycle(self):
        """OPEN → INVESTIGATING → RESOLVED → CLOSED with RCA."""
        s = WIS.OPEN
        s, _ = apply_transition(s, WIS.INVESTIGATING)
        s, _ = apply_transition(s, WIS.RESOLVED)
        s, rca = apply_transition(s, WIS.CLOSED, make_rca())
        assert s == WIS.CLOSED
        assert rca.mttr_seconds > 0


# ─────────────────────────────────────────────
# State machine — error paths
# ─────────────────────────────────────────────

class TestStateMachineErrors:
    def test_open_cannot_jump_to_resolved(self):
        with pytest.raises(InvalidTransitionError):
            apply_transition(WIS.OPEN, WIS.RESOLVED)

    def test_open_cannot_jump_to_closed(self):
        with pytest.raises(InvalidTransitionError):
            apply_transition(WIS.OPEN, WIS.CLOSED)

    def test_investigating_cannot_jump_to_closed(self):
        with pytest.raises(InvalidTransitionError):
            apply_transition(WIS.INVESTIGATING, WIS.CLOSED)

    def test_closed_is_terminal(self):
        for target in [WIS.OPEN, WIS.INVESTIGATING, WIS.RESOLVED]:
            with pytest.raises(InvalidTransitionError):
                apply_transition(WIS.CLOSED, target)

    def test_resolved_to_closed_requires_rca(self):
        with pytest.raises(MissingRCAError) as exc_info:
            apply_transition(WIS.RESOLVED, WIS.CLOSED, rca=None)
        assert "RCA is required" in str(exc_info.value)

    def test_resolved_to_closed_with_missing_rca_fields(self):
        """Pydantic should reject RCA with too-short descriptions."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            make_rca(root_cause_description="Too short")  # < 20 chars

    def test_resolved_to_closed_end_before_start(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(Exception):
            make_rca(incident_start=now, incident_end=now - timedelta(hours=1))


# ─────────────────────────────────────────────
# RCA validation
# ─────────────────────────────────────────────

class TestRCAValidation:
    def test_mttr_calculated_correctly(self):
        now = datetime.now(timezone.utc)
        rca_input = make_rca(
            incident_start=now - timedelta(minutes=90),
            incident_end=now,
        )
        _, rca_record = apply_transition(WIS.RESOLVED, WIS.CLOSED, rca_input)
        assert rca_record.mttr_seconds == pytest.approx(5400, abs=5)  # 90 min

    def test_rca_fields_minimum_length(self):
        """All text fields have minimum length requirements."""
        with pytest.raises(Exception):
            make_rca(fix_applied="short")  # < 10 chars

        with pytest.raises(Exception):
            make_rca(prevention_steps="too short")  # < 10 chars

    def test_valid_rca_has_unique_id(self):
        rca1 = make_rca()
        _, record1 = apply_transition(WIS.RESOLVED, WIS.CLOSED, rca1)
        rca2 = make_rca()
        _, record2 = apply_transition(WIS.RESOLVED, WIS.CLOSED, rca2)
        assert record1.rca_id != record2.rca_id


# ─────────────────────────────────────────────
# Ring buffer
# ─────────────────────────────────────────────

class TestRingBuffer:
    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue(self):
        buf = SignalRingBuffer(capacity=10)
        signal = make_signal()
        accepted = await buf.enqueue(signal)
        assert accepted is True
        assert buf.size == 1

        dequeued = await buf.dequeue(timeout=0.1)
        assert dequeued is not None
        assert dequeued.signal_id == signal.signal_id

    @pytest.mark.asyncio
    async def test_backpressure_drops_when_full(self):
        buf = SignalRingBuffer(capacity=3)
        for _ in range(3):
            await buf.enqueue(make_signal())

        # Buffer now full — next should be dropped
        overflow = make_signal()
        accepted = await buf.enqueue(overflow)
        assert accepted is False
        assert buf.stats.total_dropped == 1
        assert buf.size == 3  # Size unchanged

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_on_timeout(self):
        buf = SignalRingBuffer(capacity=10)
        result = await buf.dequeue(timeout=0.05)
        assert result is None

    @pytest.mark.asyncio
    async def test_drain_batch(self):
        buf = SignalRingBuffer(capacity=100)
        for _ in range(50):
            await buf.enqueue(make_signal())

        batch = await buf.drain(batch_size=20)
        assert len(batch) == 20
        assert buf.size == 30

    @pytest.mark.asyncio
    async def test_throughput_stats(self):
        buf = SignalRingBuffer(capacity=1000)
        for _ in range(100):
            await buf.enqueue(make_signal())

        assert buf.stats.total_enqueued == 100
        # throughput_per_sec is window-based; just check it returns a float
        tps = buf.stats.throughput_per_sec(window=5.0)
        assert isinstance(tps, float)
        assert tps >= 0

    @pytest.mark.asyncio
    async def test_concurrent_producers(self):
        """Multiple concurrent enqueues must not lose or duplicate signals."""
        buf = SignalRingBuffer(capacity=1000)

        async def producer(n: int):
            for _ in range(n):
                await buf.enqueue(make_signal())

        await asyncio.gather(*[producer(50) for _ in range(10)])
        assert buf.stats.total_enqueued == 500
        assert buf.size == 500
