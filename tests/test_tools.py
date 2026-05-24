import unittest

from local_agent_bench.tools import ToolError, list_directory, read_file


class ToolTest(unittest.TestCase):
    def test_lists_project_directory(self) -> None:
        entries = list_directory(".")["entries"]
        names = {entry["name"] for entry in entries}
        self.assertIn("README.md", names)

    def test_prevents_path_escape(self) -> None:
        with self.assertRaises(ToolError):
            read_file("../MEMORY.md")


if __name__ == "__main__":
    unittest.main()

