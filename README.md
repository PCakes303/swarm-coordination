# Swarm Coordination

Experimental task assignment, delegation, acknowledgement, bounded retry and lease recovery for the hybrid agent swarm.

## Initial vertical slice

This scaffold coordinates a task through injected candidate-discovery and dispatch adapters. It does not implement a network service or distributed scheduler.

- Validates bounded task declarations and attempt budgets.
- Requires an explicit policy callback returning exactly `True`.
- Resolves at most 256 candidates by default, filters the exact capability, removes duplicate agent IDs and sorts deterministically.
- Supports idempotent submission; conflicting reuse of an idempotency key is rejected.
- Binds acknowledgement, start and completion to the active dispatch reference and selected agent.
- Retries failed dispatches, reported failures and expired leases within a fixed attempt budget.
- Emits optional lifecycle audit events and fails closed when configured audit delivery fails.
- Limits the number of retained tasks and rejects non-finite/boolean lifecycle timestamps.

## Quick start

```python
from swarm_coordination import AgentCandidate, Coordinator, TaskRequest

class DemoDispatch:
    def dispatch(self, request, candidate, dispatch_ref):
        print("send", request.task_id, "to", candidate.agent_id, dispatch_ref)

agents = [
    AgentCandidate("agent.alpha", ("text.summarize",), "https://alpha.example"),
    AgentCandidate("agent.beta", ("text.summarize",), "https://beta.example"),
]
coordinator = Coordinator(
    candidate_resolver=lambda capability: agents,
    dispatch_adapter=DemoDispatch(),
    policy_check=lambda principal, task: principal == "principal.demo",
)
request = TaskRequest(
    "task.demo", "idem.demo", "principal.demo",
    "text.summarize", "artifact://input/123", max_attempts=3,
)
assignment = coordinator.submit(request)
# The selected agent's authenticated adapter calls:
coordinator.acknowledge(
    assignment.task_id, assignment.dispatch_ref, assignment.assigned_agent_id
)
coordinator.start(
    assignment.task_id, assignment.dispatch_ref, assignment.assigned_agent_id
)
coordinator.complete(
    assignment.task_id, assignment.dispatch_ref, assignment.assigned_agent_id,
    result_ref="artifact://result/123",
)
```

## AIX and transport boundary

AIX remains an extension layer. An external adapter can map requests to the AIX Core `task.request` envelope and map acknowledgement/status/result events to the corresponding lifecycle vocabulary. This scaffold does not implement an AIX codec, HTTP/MCP/A2A transport or authenticated message delivery.

## Security and reliability limits

This implementation is single-process and in-memory. Restart loses task and idempotency state. It does not authenticate requesters or agents, verify signatures, provide cross-replica replay protection, implement distributed consensus, or guarantee exactly-once delivery/execution. Lease expiry does not terminate an old worker; production adapters need fencing or idempotent side effects.

See [coordination contract](docs/COORDINATION-CONTRACT.md) and [threat model](docs/THREAT-MODEL.md). Python 3.10–3.12 are covered by CI. No release is published and the repository-specific license decision is pending review.
