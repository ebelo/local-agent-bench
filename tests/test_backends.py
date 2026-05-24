import json
import unittest
from pathlib import Path

from local_agent_bench.backends import (
    BackendError,
    CommandResult,
    HermesChatBackend,
    OpenClawChatBackend,
    extract_openclaw_response_text,
    normalize_runtime,
    redact_command_text,
    render_cli_turn_prompt,
)


class BackendTest(unittest.TestCase):
    def test_runtime_aliases(self) -> None:
        self.assertEqual(normalize_runtime("ollama"), "raw-ollama-react")
        self.assertEqual(normalize_runtime("openclaw"), "openclaw-react")
        self.assertEqual(normalize_runtime("hermes"), "hermes-react")

    def test_renders_cli_turn_prompt(self) -> None:
        prompt = render_cli_turn_prompt(
            [
                {"role": "system", "content": "Use tools."},
                {"role": "user", "content": "List files."},
            ]
        )
        self.assertIn("System:\nUse tools.", prompt)
        self.assertIn("User:\nList files.", prompt)
        self.assertIn("Next assistant message:", prompt)

    def test_extracts_openclaw_payload_text(self) -> None:
        stdout = json.dumps({"payloads": [{"text": "Final Answer: done"}]})
        self.assertEqual(extract_openclaw_response_text(stdout), "Final Answer: done")

    def test_extracts_openclaw_infer_output_text(self) -> None:
        stdout = json.dumps({"outputs": [{"text": "Final Answer: done"}]})
        self.assertEqual(extract_openclaw_response_text(stdout), "Final Answer: done")

    def test_extracts_openclaw_nested_final_text(self) -> None:
        stdout = json.dumps({"result": {"meta": {"finalAssistantVisibleText": "Action: get_cwd"}}})
        self.assertEqual(extract_openclaw_response_text(stdout), "Action: get_cwd")

    def test_openclaw_backend_builds_agent_command(self) -> None:
        calls: list[tuple[list[str], int, Path]] = []

        def runner(argv: list[str], timeout: int, cwd: Path) -> CommandResult:
            calls.append((argv, timeout, cwd))
            return CommandResult(0, json.dumps({"payloads": [{"text": "Final Answer: ok"}]}), "")

        backend = OpenClawChatBackend(binary="openclaw", timeout_seconds=30, run_command=runner)
        result = backend.chat("provider/model", [{"role": "user", "content": "Hello"}])

        self.assertEqual(result, "Final Answer: ok")
        argv = calls[0][0]
        self.assertEqual(argv[:5], ["openclaw", "infer", "model", "run", "--json"])
        self.assertIn("--local", argv)
        self.assertIn("--model", argv)
        self.assertIn("provider/model", argv)
        self.assertIn("--prompt", argv)

    def test_hermes_backend_builds_oneshot_command(self) -> None:
        calls: list[tuple[list[str], int, Path]] = []

        def runner(argv: list[str], timeout: int, cwd: Path) -> CommandResult:
            calls.append((argv, timeout, cwd))
            return CommandResult(0, "Final Answer: ok\n", "")

        backend = HermesChatBackend(binary="hermes", toolsets="safe", timeout_seconds=30, run_command=runner)
        result = backend.chat("provider/model", [{"role": "user", "content": "Hello"}])

        self.assertEqual(result, "Final Answer: ok")
        argv = calls[0][0]
        self.assertEqual(argv[0], "hermes")
        self.assertIn("chat", argv)
        self.assertIn("--query", argv)
        self.assertIn("--quiet", argv)
        self.assertIn("--model", argv)
        self.assertIn("provider/model", argv)
        self.assertIn("--toolsets", argv)
        self.assertIn("safe", argv)
        self.assertIn("--max-turns", argv)
        self.assertIn("--ignore-rules", argv)

    def test_cli_failure_raises_backend_error(self) -> None:
        def runner(argv: list[str], timeout: int, cwd: Path) -> CommandResult:
            return CommandResult(2, "", "bad runtime")

        backend = HermesChatBackend(binary="hermes", timeout_seconds=30, run_command=runner)
        with self.assertRaises(BackendError) as ctx:
            backend.chat("provider/model", [{"role": "user", "content": "Hello"}])
        self.assertEqual(ctx.exception.failure_reason, "RUNTIME_ERROR")

    def test_redacts_command_text_home(self) -> None:
        text = f"Project: {Path.home()}/runtime"
        self.assertEqual(redact_command_text(text), "Project: <HOME>/runtime")


if __name__ == "__main__":
    unittest.main()
