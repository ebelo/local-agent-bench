import unittest

from local_agent_bench.scoring import IGNORED_TOOL_RESULT, MISSING_REQUIRED_TOOL, PASS, score_task
from local_agent_bench.types import Task, ToolCall


class ScoringTest(unittest.TestCase):
    def test_scores_pass_when_required_tool_and_assertion_pass(self) -> None:
        task = Task(
            id="fs",
            category="filesystem",
            prompt="List files",
            required_tools=["list_directory"],
            assertions=[{"type": "answer_contains_all", "values": ["README.md"]}],
        )
        calls = [ToolCall(name="list_directory", args={"path": "."}, ok=True, result={})]
        score, reason, assertions = score_task(task, "README.md is present", calls, False)
        self.assertEqual(score, 1.0)
        self.assertEqual(reason, PASS)
        self.assertTrue(assertions[0]["ok"])

    def test_requires_all_required_tools(self) -> None:
        task = Task(
            id="multi",
            category="multi_step",
            prompt="Read then get weather",
            required_tools=["read_file", "get_weather"],
        )
        calls = [ToolCall(name="get_weather", args={"location": "Berlin"}, ok=True, result={})]
        score, reason, assertions = score_task(task, "Berlin", calls, False)
        self.assertEqual(score, 0.25)
        self.assertEqual(reason, MISSING_REQUIRED_TOOL)
        self.assertEqual(assertions[0]["detail"], ["read_file"])

    def test_answer_must_include_observed_tool_value(self) -> None:
        task = Task(
            id="weather",
            category="weather",
            prompt="Weather",
            required_tools=["get_weather"],
            assertions=[{"type": "answer_contains_tool_result", "tool": "get_weather", "path": "temperature_c"}],
        )
        calls = [
            ToolCall(
                name="get_weather",
                args={"location": "Berlin"},
                ok=True,
                result={"temperature_c": 12.5},
            )
        ]
        score, reason, assertions = score_task(task, "It is warm today.", calls, False)
        self.assertEqual(score, 0.75)
        self.assertEqual(reason, IGNORED_TOOL_RESULT)
        self.assertFalse(assertions[0]["ok"])

    def test_observed_tool_value_can_pass(self) -> None:
        task = Task(
            id="weather",
            category="weather",
            prompt="Weather",
            required_tools=["get_weather"],
            assertions=[{"type": "answer_contains_tool_result", "tool": "get_weather", "path": "temperature_c"}],
        )
        calls = [ToolCall(name="get_weather", args={}, ok=True, result={"temperature_c": 12.5})]
        score, reason, assertions = score_task(task, "The temperature is 12.5 C.", calls, False)
        self.assertEqual(score, 1.0)
        self.assertEqual(reason, PASS)
        self.assertTrue(assertions[0]["ok"])

    def test_numeric_tool_value_can_match_without_decimal_suffix(self) -> None:
        task = Task(
            id="weather",
            category="weather",
            prompt="Weather",
            required_tools=["get_weather"],
            assertions=[{"type": "answer_contains_tool_result", "tool": "get_weather", "path": "temperature_c"}],
        )
        calls = [ToolCall(name="get_weather", args={}, ok=True, result={"temperature_c": 27.0})]
        score, reason, _ = score_task(task, "The temperature is 27 C.", calls, False)
        self.assertEqual(score, 1.0)
        self.assertEqual(reason, PASS)

    def test_tool_result_contains_supports_list_paths(self) -> None:
        task = Task(
            id="fs",
            category="filesystem",
            prompt="List",
            required_tools=["list_directory"],
            assertions=[
                {"type": "tool_result_contains", "tool": "list_directory", "path": "entries[].name", "value": "README.md"}
            ],
        )
        calls = [
            ToolCall(
                name="list_directory",
                args={"path": "."},
                ok=True,
                result={"entries": [{"name": "README.md"}, {"name": "tests"}]},
            )
        ]
        score, reason, assertions = score_task(task, "README.md", calls, False)
        self.assertEqual(score, 1.0)
        self.assertEqual(reason, PASS)
        self.assertTrue(assertions[0]["ok"])

    def test_scores_no_tool_attempt(self) -> None:
        task = Task(id="fs", category="filesystem", prompt="List files", required_tools=["list_directory"])
        score, reason, _ = score_task(task, "I cannot access files.", [], False)
        self.assertEqual(score, 0.0)
        self.assertEqual(reason, "NO_TOOL_ATTEMPT")


if __name__ == "__main__":
    unittest.main()
