import json
import unittest

from local_agent_bench.native import (
    NATIVE_MISSING_REQUIRED_ARGUMENT,
    NATIVE_NO_TOOL_ATTEMPT,
    NATIVE_PASS,
    extract_native_tool_calls,
    score_native_platform_tools,
)
from local_agent_bench.types import Task, ToolCall


class NativePlatformScoringTest(unittest.TestCase):
    def test_extracts_openclaw_tool_call_envelope(self) -> None:
        text = json.dumps({"name": "tool_call", "arguments": {"id": "weather"}})

        calls = extract_native_tool_calls(text)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "get_weather")
        self.assertEqual(calls[0].args, {})
        self.assertFalse(calls[0].ok)

    def test_extracts_tool_call_from_openclaw_payload_text(self) -> None:
        text = json.dumps(
            {
                "payloads": [
                    {
                        "text": '```json\n{"name":"tool_call","arguments":{"id":"weather","location":"Sion"}}\n```'
                    }
                ]
            }
        )

        calls = extract_native_tool_calls(text)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "get_weather")
        self.assertEqual(calls[0].args, {"location": "Sion"})
        self.assertTrue(calls[0].ok)

    def test_scores_missing_native_tool_argument(self) -> None:
        task = Task(
            id="weather",
            category="weather",
            prompt="How is the weather in Sion now?",
            required_tools=["get_weather"],
            allowed_tools=["get_weather"],
        )
        calls = [ToolCall(name="get_weather", args={}, ok=False)]

        score = score_native_platform_tools(task, calls)

        self.assertEqual(score["score"], 0.5)
        self.assertEqual(score["failure_reason"], NATIVE_MISSING_REQUIRED_ARGUMENT)
        self.assertTrue(score["tool_intent_detected"])
        self.assertEqual(score["missing_required_arguments"][0]["missing"], ["location"])

    def test_scores_valid_native_weather_location_call(self) -> None:
        task = Task(
            id="weather",
            category="weather",
            prompt="How is the weather in Sion now?",
            required_tools=["get_weather"],
        )
        calls = [ToolCall(name="weather", args={"location": "Sion, Switzerland"}, ok=True)]

        score = score_native_platform_tools(task, calls)

        self.assertEqual(score["score"], 1.0)
        self.assertEqual(score["failure_reason"], NATIVE_PASS)

    def test_scores_no_native_tool_attempt(self) -> None:
        task = Task(id="weather", category="weather", prompt="Weather", required_tools=["get_weather"])

        score = score_native_platform_tools(task, [])

        self.assertEqual(score["score"], 0.0)
        self.assertEqual(score["failure_reason"], NATIVE_NO_TOOL_ATTEMPT)


if __name__ == "__main__":
    unittest.main()
