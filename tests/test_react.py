import unittest

from local_agent_bench.ollama import OllamaError
from local_agent_bench.react import FINAL_RE, _ollama_failure_reason, parse_action, run_task
from local_agent_bench.types import Task


class StubBackend:
    runtime = "stub-react"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.index = 0

    def chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        del model, messages, temperature
        response = self.responses[self.index]
        self.index += 1
        return response

    def metadata(self, model: str) -> dict[str, object]:
        del model
        return {}


class ReactParsingTest(unittest.TestCase):
    def test_parses_action(self) -> None:
        text = 'Thought: inspect\nAction: list_directory\nAction Input: {"path": "."}'
        name, args = parse_action(text)
        self.assertEqual(name, "list_directory")
        self.assertEqual(args, {"path": "."})

    def test_parses_nested_action_json(self) -> None:
        text = 'Action: example\nAction Input: {"outer": {"inner": true}}\nExtra text'
        name, args = parse_action(text)
        self.assertEqual(name, "example")
        self.assertEqual(args, {"outer": {"inner": True}})

    def test_parses_final_answer(self) -> None:
        text = "Final Answer: README.md exists."
        match = FINAL_RE.search(text)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.group("answer"), "README.md exists.")

    def test_classifies_missing_model(self) -> None:
        exc = OllamaError("HTTP 404: model 'missing' not found", status_code=404)
        self.assertEqual(_ollama_failure_reason(exc), "MODEL_NOT_INSTALLED")

    def test_classifies_ollama_timeout(self) -> None:
        exc = OllamaError("request timed out after 25s")
        self.assertEqual(_ollama_failure_reason(exc), "TIMEOUT")

    def test_plain_answer_after_tool_observation_is_scored(self) -> None:
        backend = StubBackend(
            [
                'Action: read_file\nAction Input: {"path": "benchmarks/fixtures.md"}',
                "The benchmark codename is alpine-signal.",
            ]
        )
        task = Task(
            id="fixture",
            category="filesystem",
            prompt="Read the fixture note and tell me the benchmark codename.",
            required_tools=["read_file"],
            allowed_tools=["read_file"],
            assertions=[{"type": "answer_contains_all", "values": ["alpine-signal"]}],
        )

        result = run_task(backend, "stub-model", task)

        self.assertEqual(result.failure_reason, "PASS")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.final_answer, "The benchmark codename is alpine-signal.")


if __name__ == "__main__":
    unittest.main()
