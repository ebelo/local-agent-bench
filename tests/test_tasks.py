import tempfile
import unittest
from pathlib import Path

from local_agent_bench.tasks import load_tasks


class TaskLoadingTest(unittest.TestCase):
    def test_loads_required_tools_and_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bench.json"
            path.write_text(
                """
                {
                  "tasks": [
                    {
                      "id": "x",
                      "category": "filesystem",
                      "prompt": "List files",
                      "required_tools": ["list_directory"],
                      "allowed_tools": ["list_directory"],
                      "requires_network": false,
                      "assertions": [{"type": "answer_contains", "value": "README.md"}]
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            task = load_tasks(path)[0]
        self.assertEqual(task.required_tools, ["list_directory"])
        self.assertEqual(task.allowed_tools, ["list_directory"])
        self.assertEqual(task.assertions[0]["type"], "answer_contains")

    def test_converts_legacy_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bench.json"
            path.write_text(
                """
                {
                  "tasks": [
                    {
                      "id": "x",
                      "category": "filesystem",
                      "prompt": "List files",
                      "expected_tools": ["list_directory"],
                      "expected_contains_any": ["README.md"]
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            task = load_tasks(path)[0]
        self.assertEqual(task.required_tools, ["list_directory"])
        self.assertEqual(task.assertions[0]["type"], "answer_contains_any")

    def test_loads_platform_native_ladder_suite(self) -> None:
        tasks = load_tasks(Path("benchmarks/platform_native_ladder.json"))

        self.assertEqual(len(tasks), 7)
        self.assertEqual(
            [task.diagnostic_layer for task in tasks],
            [
                "platform_native_ladder_level_6",
                "platform_native_ladder_level_6",
                "platform_native_ladder_level_6",
                "platform_native_ladder_level_7",
                "platform_native_ladder_level_7",
                "platform_native_ladder_level_8",
                "platform_native_ladder_level_8",
            ],
        )
        self.assertTrue(any(task.requires_network for task in tasks))


if __name__ == "__main__":
    unittest.main()
