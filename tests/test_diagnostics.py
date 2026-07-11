import unittest
from unittest.mock import patch

from local_agent_bench.diagnostics import run_diagnostics


class FakeOllamaClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def version(self) -> str:
        return "0.31.1"

    def list_models(self) -> list[str]:
        return ["qwen2.5-coder:7b"]


class DiagnosticsTest(unittest.TestCase):
    def test_raw_ollama_preflight_uses_api_not_cli(self) -> None:
        with patch("local_agent_bench.diagnostics.OllamaClient", FakeOllamaClient):
            checks = run_diagnostics(
                "http://ollama:11434",
                "qwen2.5-coder:7b",
                requires_network=False,
                runtime="raw-ollama-react",
            )

        by_name = {check.name: check for check in checks}
        self.assertNotIn("ollama_cli", by_name)
        self.assertTrue(by_name["ollama_api_version"].ok)
        self.assertTrue(by_name["ollama_api"].ok)
        self.assertTrue(by_name["model_installed"].ok)

    def test_pi_native_uses_pi_command_check(self) -> None:
        with patch("local_agent_bench.diagnostics.shutil.which", return_value="/usr/local/bin/pi"), patch(
            "local_agent_bench.diagnostics.command_output",
            return_value="0.80.3",
        ):
            checks = run_diagnostics(
                "http://ollama:11434",
                "ollama/qwen2.5-coder:7b",
                requires_network=False,
                runtime="pi-native",
            )

        by_name = {check.name: check for check in checks}
        self.assertTrue(by_name["pi_cli"].ok)
        self.assertEqual(by_name["pi_cli"].detail, "0.80.3")


if __name__ == "__main__":
    unittest.main()
