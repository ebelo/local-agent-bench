import unittest
from pathlib import Path
from unittest.mock import patch

from local_agent_bench.backends import CommandResult
from local_agent_bench.judge import _parse_judge_response
from local_agent_bench.platform_native import PLATFORM_NATIVE_PASS, run_platform_native_task
from local_agent_bench.tasks import load_tasks
from local_agent_bench.types import Task


class FakeNativeBackend:
    runtime = "pi-native"

    def native_turn(self, model: str, prompt: str) -> CommandResult:
        return CommandResult(0, "README.md\nbenchmarks\nlocal_agent_bench\n", "")

    def metadata(self, model: str) -> dict[str, object]:
        return {}


class FakePlanOnlyBackend:
    runtime = "pi-native"

    def native_turn(self, model: str, prompt: str) -> CommandResult:
        return CommandResult(0, "I will use curl to fetch the weather later.", "")

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
        self.assertEqual(result.native_platform_tool_score["judge_score_before_guardrails"], 1.0)

    def test_guardrails_cap_passing_judge(self) -> None:
        task = Task(
            id="native_weather_plan_only",
            category="weather",
            prompt="Get weather.",
            assertions=[{"type": "answer_not_contains_any", "values": ["will use curl"]}],
        )
        with patch(
            "local_agent_bench.platform_native.judge_native_result",
            return_value={
                "judge_score": 1.0,
                "judge_verdict": "JUDGE_PASS",
                "judge_reasoning": "Claims to use curl.",
                "judge_model": "test-judge",
            },
        ):
            result = run_platform_native_task(FakePlanOnlyBackend(), "ollama/test", task)

        self.assertEqual(result.score, 0.5)
        self.assertEqual(result.failure_reason, "PLATFORM_NATIVE_PARTIAL")
        self.assertEqual(result.native_platform_tool_score["judge_score_before_guardrails"], 1.0)
        self.assertEqual(result.native_platform_tool_score["deterministic_reason"], "ASSERTION_FAILED")

    def test_deterministic_score_only_skips_judge(self) -> None:
        task = Task(
            id="native_latency_current_directory",
            category="latency",
            prompt="What is cwd?",
            assertions=[{"type": "answer_contains_any", "values": ["README.md"]}],
        )
        with patch("local_agent_bench.platform_native.judge_native_result") as judge:
            result = run_platform_native_task(
                FakeNativeBackend(),
                "ollama/test",
                task,
                deterministic_score_only=True,
            )

        judge.assert_not_called()
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.failure_reason, "PASS")
        self.assertIsNone(result.native_platform_tool_score["judge"])

    def test_unstructured_negative_judge_response_is_fail_not_error(self) -> None:
        verdict = _parse_judge_response("The response does not accomplish the task because it only lists files.")

        self.assertEqual(verdict["judge_verdict"], "JUDGE_FAIL")
        self.assertEqual(verdict["judge_score"], 0.0)

    def test_unparseable_judge_response_is_conservative_fail(self) -> None:
        verdict = _parse_judge_response("This is not a JSON verdict.")

        self.assertEqual(verdict["judge_verdict"], "JUDGE_FAIL")
        self.assertEqual(verdict["judge_score"], 0.0)

    def test_native_prompts_are_candid_user_requests(self) -> None:
        benchmark_paths = [
            Path("benchmarks/platform_native.json"),
            Path("benchmarks/platform_native_ladder.json"),
            Path("benchmarks/platform_native_reality.json"),
        ]
        forbidden_prompt_phrases = [
            "use curl",
            "native HTTP/API",
            "structured weather API",
            "prefer this",
            "Open-Meteo endpoint",
            "do not return raw json",
            "evidence line",
        ]

        for path in benchmark_paths:
            for task in load_tasks(path):
                prompt = task.prompt.casefold()
                for phrase in forbidden_prompt_phrases:
                    self.assertNotIn(phrase.casefold(), prompt, f"{path}:{task.id}")


if __name__ == "__main__":
    unittest.main()
