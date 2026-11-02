import unittest

from swarm_coordination import (
    AgentCandidate, CoordinationError, Coordinator, TaskRequest, TaskState, ValidationError,
)


A = AgentCandidate("agent.alpha", ("text.summarize",), "https://alpha.example")
B = AgentCandidate("agent.beta", ("text.summarize",), "https://beta.example")
OTHER = AgentCandidate("agent.gamma", ("code.review",), "https://gamma.example")


class FakeDispatch:
    def __init__(self, fail_agents=()):
        self.fail_agents = set(fail_agents)
        self.calls = []

    def dispatch(self, request, candidate, dispatch_ref):
        self.calls.append((candidate.agent_id, dispatch_ref))
        if candidate.agent_id in self.fail_agents:
            raise RuntimeError("synthetic dispatch failure")


def request(task="task.one", key="idem.one", attempts=3):
    return TaskRequest(task, key, "principal.coordinator", "text.summarize", "artifact://input/1", attempts)


def make_coordinator(adapter=None, candidates=None, **kwargs):
    return Coordinator(
        candidate_resolver=lambda capability: candidates if candidates is not None else [B, A, A, OTHER],
        dispatch_adapter=adapter or FakeDispatch(),
        policy_check=lambda principal, task: True,
        **kwargs,
    )


class CoordinatorTests(unittest.TestCase):

    def test_nonfinite_or_boolean_lifecycle_timestamp_is_rejected(self):
        coordinator = make_coordinator()
        with self.assertRaises(ValidationError):
            coordinator.submit(request(), now=float("nan"))
        with self.assertRaises(ValidationError):
            coordinator.submit(request(), now=True)

    def test_candidate_discovery_is_bounded(self):
        coordinator = Coordinator(
            candidate_resolver=lambda capability: (candidate for candidate in [A, B]),
            dispatch_adapter=FakeDispatch(),
            policy_check=lambda principal, task: True,
            max_candidates=1,
        )
        with self.assertRaises(CoordinationError):
            coordinator.submit(request(), now=100)

    def test_invalid_candidate_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            Coordinator(
                candidate_resolver=lambda capability: [A],
                dispatch_adapter=FakeDispatch(),
                policy_check=lambda principal, task: True,
                max_candidates=0,
            )


    def test_dispatch_audit_failure_fails_closed_without_retry(self):
        adapter = FakeDispatch()
        def audit(event):
            if event["event"] == "task.dispatching":
                raise RuntimeError("audit unavailable")
        coordinator = make_coordinator(adapter, audit_sink=audit)
        with self.assertRaises(CoordinationError):
            coordinator.submit(request(), now=100)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(coordinator.get("task.one").state, TaskState.FAILED)

    def test_two_agent_delegation_acknowledgement_and_completion(self):
        adapter = FakeDispatch()
        coordinator = make_coordinator(adapter)
        submitted = coordinator.submit(request(), now=100)
        self.assertEqual(submitted.state, TaskState.ASSIGNED)
        self.assertEqual(submitted.assigned_agent_id, "agent.alpha")
        acknowledged = coordinator.acknowledge("task.one", submitted.dispatch_ref, "agent.alpha", now=101)
        self.assertEqual(acknowledged.state, TaskState.ACKNOWLEDGED)
        running = coordinator.start("task.one", submitted.dispatch_ref, "agent.alpha", now=102)
        self.assertEqual(running.state, TaskState.RUNNING)
        failed = coordinator.complete("task.one", submitted.dispatch_ref, "agent.alpha", success=False, now=102)
        self.assertEqual(failed.state, TaskState.ASSIGNED)
        self.assertEqual(failed.assigned_agent_id, "agent.beta")
        coordinator.acknowledge("task.one", failed.dispatch_ref, "agent.beta", now=103)
        coordinator.start("task.one", failed.dispatch_ref, "agent.beta", now=104)
        completed = coordinator.complete("task.one", failed.dispatch_ref, "agent.beta", result_ref="artifact://result/1", now=104)
        self.assertEqual(completed.state, TaskState.SUCCEEDED)
        self.assertEqual(completed.result_ref, "artifact://result/1")
        self.assertEqual([c[0] for c in adapter.calls], ["agent.alpha", "agent.beta"])

    def test_idempotent_submit_returns_same_task(self):
        coordinator = make_coordinator()
        first = coordinator.submit(request(), now=100)
        second = coordinator.submit(request(), now=101)
        self.assertEqual(first, second)

    def test_idempotency_key_conflict_rejected(self):
        coordinator = make_coordinator()
        coordinator.submit(request(), now=100)
        with self.assertRaises(CoordinationError):
            coordinator.submit(request(task="task.other"), now=101)

    def test_wrong_agent_cannot_acknowledge_assignment(self):
        coordinator = make_coordinator()
        submitted = coordinator.submit(request(), now=100)
        with self.assertRaises(CoordinationError):
            coordinator.acknowledge("task.one", submitted.dispatch_ref, "agent.beta", now=101)

    def test_stale_dispatch_reference_cannot_acknowledge(self):
        coordinator = make_coordinator()
        submitted = coordinator.submit(request(), now=100)
        with self.assertRaises(CoordinationError):
            coordinator.acknowledge("task.one", "task.one:attempt:999", "agent.alpha", now=101)

    def test_expired_acknowledgement_cannot_start(self):
        coordinator = make_coordinator()
        submitted = coordinator.submit(request(), now=100)
        coordinator.acknowledge("task.one", submitted.dispatch_ref, "agent.alpha", now=101)
        with self.assertRaises(CoordinationError):
            coordinator.start("task.one", submitted.dispatch_ref, "agent.alpha", now=162)

    def test_lease_recovery_reassigns_to_next_agent(self):
        coordinator = make_coordinator()
        submitted = coordinator.submit(request(), now=100)
        recovered = coordinator.recover(now=161)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].state, TaskState.ASSIGNED)
        self.assertEqual(recovered[0].assigned_agent_id, "agent.beta")
        with self.assertRaises(CoordinationError):
            coordinator.acknowledge("task.one", submitted.dispatch_ref, "agent.alpha", now=162)

    def test_retry_budget_exhaustion(self):
        adapter = FakeDispatch(fail_agents={"agent.alpha", "agent.beta"})
        coordinator = make_coordinator(adapter, candidates=[A, B])
        submitted = coordinator.submit(request(attempts=2), now=100)
        self.assertEqual(submitted.state, TaskState.FAILED)
        self.assertEqual(submitted.attempt_count, 2)

    def test_missing_policy_denies(self):
        coordinator = Coordinator(candidate_resolver=lambda cap: [A], dispatch_adapter=FakeDispatch(), policy_check=None)
        with self.assertRaises(PermissionError):
            coordinator.submit(request(), now=100)

    def test_policy_exception_denies(self):
        def broken(principal, task):
            raise RuntimeError("policy unavailable")
        coordinator = Coordinator(candidate_resolver=lambda cap: [A], dispatch_adapter=FakeDispatch(), policy_check=broken)
        with self.assertRaises(PermissionError):
            coordinator.submit(request(), now=100)

    def test_no_candidate_fails_without_dispatch(self):
        adapter = FakeDispatch()
        coordinator = make_coordinator(adapter, candidates=[OTHER])
        submitted = coordinator.submit(request(), now=100)
        self.assertEqual(submitted.state, TaskState.FAILED)
        self.assertEqual(adapter.calls, [])

    def test_audit_failure_prevents_dispatch(self):
        adapter = FakeDispatch()
        def broken(event):
            raise RuntimeError("audit unavailable")
        coordinator = make_coordinator(adapter, audit_sink=broken)
        with self.assertRaises(RuntimeError):
            coordinator.submit(request(), now=100)
        self.assertEqual(adapter.calls, [])

    def test_task_capacity_is_bounded(self):
        coordinator = make_coordinator(max_tasks=1)
        coordinator.submit(request(), now=100)
        with self.assertRaises(CoordinationError):
            coordinator.submit(request(task="task.two", key="idem.two"), now=101)

    def test_overflowing_integer_lifecycle_timestamp_is_rejected(self):
        coordinator = make_coordinator()
        with self.assertRaises(ValidationError):
            coordinator.submit(request(), now=10**10000)


if __name__ == "__main__":
    unittest.main()
