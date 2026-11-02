"""Bounded task and candidate contracts."""
from dataclasses import dataclass
from enum import Enum
import re

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CAPABILITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ValidationError(ValueError):
    """Raised when a task or candidate violates the contract."""


class CoordinationError(RuntimeError):
    """Raised when a lifecycle transition is invalid or cannot proceed."""


class TaskState(str, Enum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    ACKNOWLEDGED = "acknowledged"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class TaskRequest:
    task_id: str
    idempotency_key: str
    requester_id: str
    capability_id: str
    workload_ref: str
    max_attempts: int = 3

    def validate(self) -> None:
        for name, value in (
            ("task_id", self.task_id),
            ("idempotency_key", self.idempotency_key),
            ("requester_id", self.requester_id),
            ("capability_id", self.capability_id),
        ):
            pattern = _CAPABILITY if name == "capability_id" else _ID
            if not isinstance(value, str) or not pattern.fullmatch(value):
                raise ValidationError(f"{name} must be a bounded identifier")
        if not isinstance(self.workload_ref, str) or not self.workload_ref.strip() or len(self.workload_ref) > 512:
            raise ValidationError("workload_ref must contain 1..512 characters")
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool) or not 1 <= self.max_attempts <= 5:
            raise ValidationError("max_attempts must be an integer in [1, 5]")


@dataclass(frozen=True)
class AgentCandidate:
    agent_id: str
    capability_ids: tuple[str, ...]
    endpoint_ref: str

    def validate(self) -> None:
        if not isinstance(self.agent_id, str) or not _ID.fullmatch(self.agent_id):
            raise ValidationError("agent_id must be a bounded identifier")
        if not isinstance(self.endpoint_ref, str) or not self.endpoint_ref.strip() or len(self.endpoint_ref) > 512:
            raise ValidationError("endpoint_ref must contain 1..512 characters")
        if not isinstance(self.capability_ids, tuple) or len(self.capability_ids) > 128:
            raise ValidationError("capability_ids must be a tuple of at most 128 entries")
        for capability in self.capability_ids:
            if not isinstance(capability, str) or not _CAPABILITY.fullmatch(capability):
                raise ValidationError("candidate capability identifier is invalid")


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    idempotency_key: str
    state: TaskState
    attempt_count: int
    max_attempts: int
    assigned_agent_id: str | None
    dispatch_ref: str | None
    lease_expires_at: float | None
    result_ref: str | None
    last_error: str | None
