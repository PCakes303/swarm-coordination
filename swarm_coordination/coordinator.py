"""Bounded, deterministic task coordinator with explicit adapter seams."""
from dataclasses import dataclass, field
import math
import threading
import time
from typing import Callable, Iterable, Protocol

from .models import (
    AgentCandidate, CoordinationError, TaskRequest, TaskSnapshot, TaskState, ValidationError,
)


class DispatchAdapter(Protocol):
    def dispatch(self, request: TaskRequest, candidate: AgentCandidate, dispatch_ref: str) -> None: ...


CandidateResolver = Callable[[str], Iterable[AgentCandidate]]
PolicyCheck = Callable[[str, TaskRequest], bool]
AuditSink = Callable[[dict], None]


@dataclass
class _TaskRecord:
    request: TaskRequest
    candidates: tuple[AgentCandidate, ...]
    state: TaskState = TaskState.QUEUED
    attempt_count: int = 0
    assigned_agent_id: str | None = None
    dispatch_ref: str | None = None
    lease_expires_at: float | None = None
    result_ref: str | None = None
    last_error: str | None = None
    history: list[str] = field(default_factory=list)

    def snapshot(self) -> TaskSnapshot:
        return TaskSnapshot(
            task_id=self.request.task_id,
            idempotency_key=self.request.idempotency_key,
            state=self.state,
            attempt_count=self.attempt_count,
            max_attempts=self.request.max_attempts,
            assigned_agent_id=self.assigned_agent_id,
            dispatch_ref=self.dispatch_ref,
            lease_expires_at=self.lease_expires_at,
            result_ref=self.result_ref,
            last_error=self.last_error,
        )


class Coordinator:
    """Single-process coordinator; persistence and authenticated transport are external."""

    def __init__(
        self,
        *,
        candidate_resolver: CandidateResolver,
        dispatch_adapter: DispatchAdapter,
        policy_check: PolicyCheck | None,
        audit_sink: AuditSink | None = None,
        max_tasks: int = 256,
        max_candidates: int = 256,
        lease_seconds: int = 60,
    ):
        if not callable(candidate_resolver):
            raise TypeError("candidate_resolver must be callable")
        if not callable(getattr(dispatch_adapter, "dispatch", None)):
            raise TypeError("dispatch_adapter must implement dispatch(request, candidate, dispatch_ref)")
        if not isinstance(max_tasks, int) or isinstance(max_tasks, bool) or not 1 <= max_tasks <= 10000:
            raise ValueError("max_tasks must be an integer in [1, 10000]")
        if not isinstance(max_candidates, int) or isinstance(max_candidates, bool) or not 1 <= max_candidates <= 4096:
            raise ValueError("max_candidates must be an integer in [1, 4096]")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be an integer in [1, 3600]")
        self.candidate_resolver = candidate_resolver
        self.dispatch_adapter = dispatch_adapter
        self.policy_check = policy_check
        self.audit_sink = audit_sink
        self.max_tasks = max_tasks
        self.max_candidates = max_candidates
        self.lease_seconds = lease_seconds
        self._tasks: dict[str, _TaskRecord] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = threading.RLock()

    def _emit(self, event: str, record: _TaskRecord, **extra) -> None:
        if self.audit_sink is not None:
            payload = {
                "event": event,
                "task_id": record.request.task_id,
                "requester_id": record.request.requester_id,
                "attempt_count": record.attempt_count,
                "state": record.state.value,
            }
            payload.update(extra)
            self.audit_sink(payload)

    @staticmethod
    def _timestamp(now: float | None) -> float:
        value = time.time() if now is None else now
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValidationError("timestamp must be a finite number")
        return float(value)

    def _candidates(self, capability_id: str) -> tuple[AgentCandidate, ...]:
        try:
            discovered = iter(self.candidate_resolver(capability_id))
        except Exception as exc:
            raise CoordinationError("candidate discovery failed") from exc
        unique: dict[str, AgentCandidate] = {}
        for index, candidate in enumerate(discovered):
            if index >= self.max_candidates:
                raise CoordinationError("candidate discovery exceeded configured limit")
            if not isinstance(candidate, AgentCandidate):
                continue
            try:
                candidate.validate()
            except ValidationError:
                continue
            if capability_id in candidate.capability_ids:
                unique.setdefault(candidate.agent_id, candidate)
        return tuple(unique[key] for key in sorted(unique))

    def submit(self, request: TaskRequest, *, now: float | None = None) -> TaskSnapshot:
        request.validate()
        if self.policy_check is None:
            raise PermissionError("policy unavailable; task submission denied")
        try:
            allowed = self.policy_check(request.requester_id, request)
        except Exception as exc:
            raise PermissionError("policy evaluation failed; task submission denied") from exc
        if allowed is not True:
            raise PermissionError("policy denied task submission")
        timestamp = self._timestamp(now)

        with self._lock:
            existing_id = self._idempotency.get(request.idempotency_key)
            if existing_id is not None:
                existing = self._tasks[existing_id]
                if existing.request != request:
                    raise CoordinationError("idempotency key already belongs to a different task request")
                return existing.snapshot()
            if request.task_id in self._tasks:
                raise CoordinationError("task_id already exists")
            if len(self._tasks) >= self.max_tasks:
                raise CoordinationError("coordinator task capacity reached")
            candidates = self._candidates(request.capability_id)
            record = _TaskRecord(request=request, candidates=candidates)
            self._tasks[request.task_id] = record
            self._idempotency[request.idempotency_key] = request.task_id
            try:
                self._emit("task.accepted", record)
            except Exception:
                del self._tasks[request.task_id]
                del self._idempotency[request.idempotency_key]
                raise
            if not candidates:
                record.state = TaskState.FAILED
                record.last_error = "no eligible candidate"
                self._emit("task.failed", record, reason="no_eligible_candidate")
                return record.snapshot()
            self._dispatch_next(record, timestamp)
            return record.snapshot()

    def _dispatch_next(self, record: _TaskRecord, now: float) -> None:
        while record.attempt_count < record.request.max_attempts:
            index = record.attempt_count % len(record.candidates)
            candidate = record.candidates[index]
            record.attempt_count += 1
            dispatch_ref = f"{record.request.task_id}:attempt:{record.attempt_count}"
            record.assigned_agent_id = candidate.agent_id
            record.dispatch_ref = dispatch_ref
            record.lease_expires_at = now + self.lease_seconds
            record.state = TaskState.QUEUED
            try:
                self._emit("task.dispatching", record, agent_id=candidate.agent_id, dispatch_ref=dispatch_ref)
                self.dispatch_adapter.dispatch(record.request, candidate, dispatch_ref)
            except Exception as exc:
                record.last_error = f"dispatch failed: {type(exc).__name__}"
                record.history.append(record.last_error)
                record.state = TaskState.QUEUED
                continue
            record.state = TaskState.ASSIGNED
            record.last_error = None
            return
        record.state = TaskState.FAILED
        record.lease_expires_at = None
        record.last_error = record.last_error or "attempt budget exhausted"
        self._emit("task.failed", record, reason="attempt_budget_exhausted")

    def _active(self, task_id: str, dispatch_ref: str, agent_id: str, expected: TaskState) -> _TaskRecord:
        record = self._tasks.get(task_id)
        if record is None:
            raise CoordinationError("unknown task")
        if record.state != expected:
            raise CoordinationError(f"task state must be {expected.value}")
        if record.dispatch_ref != dispatch_ref or record.assigned_agent_id != agent_id:
            raise CoordinationError("dispatch reference or assigned agent does not match active attempt")
        return record

    def acknowledge(self, task_id: str, dispatch_ref: str, agent_id: str, *, now: float | None = None) -> TaskSnapshot:
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            record = self._active(task_id, dispatch_ref, agent_id, TaskState.ASSIGNED)
            if record.lease_expires_at is not None and timestamp >= record.lease_expires_at:
                raise CoordinationError("assignment lease has expired")
            self._emit("task.acknowledged", record, agent_id=agent_id, dispatch_ref=dispatch_ref)
            record.state = TaskState.ACKNOWLEDGED
            record.lease_expires_at = timestamp + self.lease_seconds
            return record.snapshot()

    def start(self, task_id: str, dispatch_ref: str, agent_id: str, *, now: float | None = None) -> TaskSnapshot:
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            record = self._active(task_id, dispatch_ref, agent_id, TaskState.ACKNOWLEDGED)
            if record.lease_expires_at is not None and timestamp >= record.lease_expires_at:
                raise CoordinationError("acknowledgement lease has expired")
            self._emit("task.started", record, agent_id=agent_id, dispatch_ref=dispatch_ref)
            record.state = TaskState.RUNNING
            return record.snapshot()

    def complete(
        self,
        task_id: str,
        dispatch_ref: str,
        agent_id: str,
        *,
        result_ref: str | None = None,
        success: bool = True,
        now: float | None = None,
    ) -> TaskSnapshot:
        timestamp = time.time() if now is None else float(now)
        if result_ref is not None and (not isinstance(result_ref, str) or len(result_ref) > 512):
            raise ValidationError("result_ref must be a string of at most 512 characters")
        if not isinstance(success, bool):
            raise ValidationError("success must be a boolean")
        with self._lock:
            record = self._active(task_id, dispatch_ref, agent_id, TaskState.RUNNING)
            if record.lease_expires_at is not None and timestamp >= record.lease_expires_at:
                raise CoordinationError("execution lease has expired")
            if success:
                self._emit("task.succeeded", record, agent_id=agent_id, dispatch_ref=dispatch_ref)
                record.state = TaskState.SUCCEEDED
                record.result_ref = result_ref
                record.lease_expires_at = None
                record.last_error = None
            else:
                self._emit("task.attempt_failed", record, agent_id=agent_id, dispatch_ref=dispatch_ref)
                record.last_error = "agent reported attempt failure"
                record.history.append(record.last_error)
                self._dispatch_next(record, timestamp)
            return record.snapshot()

    def recover(self, *, now: float | None = None) -> list[TaskSnapshot]:
        timestamp = time.time() if now is None else float(now)
        recovered = []
        with self._lock:
            for record in self._tasks.values():
                if record.state in (TaskState.ASSIGNED, TaskState.ACKNOWLEDGED, TaskState.RUNNING):
                    if record.lease_expires_at is not None and timestamp >= record.lease_expires_at:
                        self._emit("task.lease_expired", record, dispatch_ref=record.dispatch_ref)
                        record.last_error = "attempt lease expired"
                        record.history.append(record.last_error)
                        self._dispatch_next(record, timestamp)
                        recovered.append(record.snapshot())
        return recovered

    def get(self, task_id: str) -> TaskSnapshot:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise CoordinationError("unknown task")
            return record.snapshot()
