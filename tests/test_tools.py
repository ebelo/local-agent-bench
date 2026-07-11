import unittest
import urllib.error
from unittest.mock import patch

from local_agent_bench.tools import ToolError, _get_json, list_directory, read_file


class ToolTest(unittest.TestCase):
    def test_lists_project_directory(self) -> None:
        entries = list_directory(".")["entries"]
        names = {entry["name"] for entry in entries}
        self.assertIn("README.md", names)

    def test_prevents_path_escape(self) -> None:
        with self.assertRaises(ToolError):
            read_file("../MEMORY.md")

    def test_http_error_is_tool_error(self) -> None:
        error = urllib.error.HTTPError("https://api.example.test/weather", 504, "Gateway Time-out", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ToolError) as raised:
                _get_json("https://api.example.test/weather")
        self.assertIn("HTTP 504", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
