import unittest
from pathlib import Path

from local_agent_bench.redaction import redact_local_context


class RedactionTest(unittest.TestCase):
    def test_redacts_project_root_and_home(self) -> None:
        project_root = Path.home() / "workspace" / "local-agent-bench"
        data = {
            "path": str(project_root / "README.md"),
            "transcript": [f"Observation: {project_root}"],
        }
        redacted = redact_local_context(data, project_root)
        self.assertEqual(redacted["path"], "<PROJECT_ROOT>/README.md")
        self.assertEqual(redacted["transcript"], ["Observation: <PROJECT_ROOT>"])


if __name__ == "__main__":
    unittest.main()
