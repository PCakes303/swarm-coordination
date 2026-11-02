import unittest
from swarm_coordination import AgentCandidate, TaskRequest, ValidationError


class ModelTests(unittest.TestCase):
    def test_valid_request(self):
        TaskRequest("task.one", "idem.one", "principal.one", "text.summarize", "artifact://input/1").validate()

    def test_attempt_budget_is_bounded(self):
        with self.assertRaises(ValidationError):
            TaskRequest("task.one", "idem.one", "principal.one", "text.summarize", "artifact://input/1", 6).validate()

    def test_boolean_attempt_budget_rejected(self):
        with self.assertRaises(ValidationError):
            TaskRequest("task.one", "idem.one", "principal.one", "text.summarize", "artifact://input/1", True).validate()

    def test_candidate_requires_capability_tuple(self):
        with self.assertRaises(ValidationError):
            AgentCandidate("agent.one", ["text.summarize"], "https://agent.example").validate()


if __name__ == "__main__":
    unittest.main()
