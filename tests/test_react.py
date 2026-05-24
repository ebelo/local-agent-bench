import unittest

from local_agent_bench.ollama import OllamaError
from local_agent_bench.react import FINAL_RE, _ollama_failure_reason, parse_action


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


if __name__ == "__main__":
    unittest.main()
