import unittest
from unittest.mock import patch

from local_agent_bench.backends import CommandResult
from local_agent_bench.platform_native import PLATFORM_NATIVE_PASS, run_platform_native_task
from local_agent_bench.types import Task


class FakeNativeBackend:
    runtime = "pi-native"

    def native_turn(self, model: str, prompt: str) -> CommandResult:
        return CommandResult(0, "README.md\nbenchmarks\nlocal_agent_bench\n", "")

    def metadata(self, model: str) -> dict[str, object]:
        return {}


class PlatformNativeTest(unittest.TestCase):
    def test_uses_judge_as_primary_score_and_keeps_assertions(self) -> None:
        task = Task(
            id="native_list_project",
            category="filesystem",
            prompt="List project files.",
            assertions=[{"type": "answer_contains_all", "values": ["README.md", "benchmarks"]}],
        )
        with patch(
            "local_agent_bench.platform_native.judge_native_result",
            return_value={
                "judge_score": 1.0,
                "judge_verdict": "JUDGE_PASS",
                "judge_reasoning": "Listed the project files.",
                "judge_model": "test-judge",
            },
        ):
            result = run_platform_native_task(FakeNativeBackend(), "ollama/test", task)

        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.failure_reason, PLATFORM_NATIVE_PASS)
        self.assertTrue(result.assertion_results[0]["ok"])
        self.assertEqual(result.native_platform_tool_score["deterministic_score"], 1.0)
        self.assertEqual(result.native_platform_tool_score["judge"]["judge_verdict"], "JUDGE_PASS")


if __name__ == "__main__":
    unittest.main()
