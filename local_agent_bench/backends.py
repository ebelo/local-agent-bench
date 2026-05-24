from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from local_agent_bench.ollama import OllamaClient, OllamaError


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_OLLAMA_REACT = "raw-ollama-react"
OPENCLAW_REACT = "openclaw-react"
HERMES_REACT = "hermes-react"
OPENCLAW_NATIVE = "openclaw-native"
HERMES_NATIVE = "hermes-native"

RUNTIME_ALIASES = {
    "raw-ollama": RAW_OLLAMA_REACT,
    "ollama": RAW_OLLAMA_REACT,
    RAW_OLLAMA_REACT: RAW_OLLAMA_REACT,
    "openclaw": OPENCLAW_REACT,
    OPENCLAW_REACT: OPENCLAW_REACT,
    OPENCLAW_NATIVE: OPENCLAW_NATIVE,
    "hermes": HERMES_REACT,
    HERMES_REACT: HERMES_REACT,
    HERMES_NATIVE: HERMES_NATIVE,
}


class ChatBackend(Protocol):
    runtime: str

    def chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        ...

    def metadata(self, model: str) -> dict[str, Any]:
        ...


class BackendError(RuntimeError):
    def __init__(self, message: str, failure_reason: str = "RUNTIME_ERROR") -> None:
        super().__init__(message)
        self.failure_reason = failure_reason


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str], int, Path], CommandResult]


class OllamaChatBackend:
    runtime = RAW_OLLAMA_REACT

    def __init__(self, base_url: str) -> None:
        self.client = OllamaClient(base_url)

    def chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        try:
            return self.client.chat(model, messages, temperature=temperature)
        except OllamaError as exc:
            raise BackendError(str(exc), _ollama_failure_reason(exc)) from exc

    def metadata(self, model: str) -> dict[str, Any]:
        model_info = _model_info(self.client, model)
        return {
            "ollama_version": command_output(["ollama", "--version"]),
            "model_details": model_info.get("details", {}),
            "model_info": model_info.get("model_info", {}),
        }


class OpenClawChatBackend:
    runtime = OPENCLAW_REACT

    def __init__(
        self,
        *,
        binary: str | None = None,
        timeout_seconds: int = 600,
        run_command: CommandRunner | None = None,
    ) -> None:
        self.binary = binary or os.environ.get("LOCAL_AGENT_BENCH_OPENCLAW_BIN", "openclaw")
        self.timeout_seconds = timeout_seconds
        self._run_command = run_command or run_subprocess

    def chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        del temperature
        prompt = render_cli_turn_prompt(messages)
        argv = [
            self.binary,
            "infer",
            "model",
            "run",
            "--json",
            "--local",
            "--model",
            model,
            "--prompt",
            prompt,
        ]
        thinking = os.environ.get("LOCAL_AGENT_BENCH_OPENCLAW_THINKING")
        if thinking:
            argv.extend(["--thinking", thinking])
        result = _run_cli(argv, self.timeout_seconds + 15, self._run_command)
        return extract_openclaw_response_text(result.stdout)

    def metadata(self, model: str) -> dict[str, Any]:
        return {
            "adapter": self.runtime,
            "model": model,
            "openclaw_version": command_output([self.binary, "--version"]),
            "openclaw_mode": "infer model run --local --json",
        }


class HermesChatBackend:
    runtime = HERMES_REACT

    def __init__(
        self,
        *,
        binary: str | None = None,
        toolsets: str | None = None,
        timeout_seconds: int = 600,
        run_command: CommandRunner | None = None,
    ) -> None:
        self.binary = binary or os.environ.get("LOCAL_AGENT_BENCH_HERMES_BIN", "hermes")
        self.toolsets = toolsets or os.environ.get("LOCAL_AGENT_BENCH_HERMES_TOOLSETS", "safe")
        self.timeout_seconds = timeout_seconds
        self._run_command = run_command or run_subprocess

    def chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        del temperature
        prompt = render_cli_turn_prompt(messages)
        argv = [
            self.binary,
            "chat",
            "--query",
            prompt,
            "--quiet",
            "--model",
            model,
            "--toolsets",
            self.toolsets,
            "--max-turns",
            "1",
            "--ignore-rules",
            "--source",
            "local-agent-bench",
        ]
        result = _run_cli(argv, self.timeout_seconds, self._run_command)
        return result.stdout.strip()

    def metadata(self, model: str) -> dict[str, Any]:
        return {
            "adapter": self.runtime,
            "model": model,
            "hermes_version": command_output([self.binary, "--version"]),
            "hermes_mode": "chat --query --quiet --ignore-rules",
            "hermes_toolsets": self.toolsets,
        }


class OpenClawNativeBackend:
    runtime = OPENCLAW_NATIVE

    def __init__(
        self,
        *,
        binary: str | None = None,
        timeout_seconds: int = 600,
        run_command: CommandRunner | None = None,
    ) -> None:
        self.binary = binary or os.environ.get("LOCAL_AGENT_BENCH_OPENCLAW_BIN", "openclaw")
        self.timeout_seconds = timeout_seconds
        self._run_command = run_command or run_subprocess

    def native_turn(self, model: str, prompt: str) -> CommandResult:
        argv = [
            self.binary,
            "agent",
            "--local",
            "--json",
            "--model",
            model,
            "--session-key",
            f"local-agent-bench:{os.getpid()}:{uuid.uuid4().hex}",
            "--message",
            prompt,
        ]
        thinking = os.environ.get("LOCAL_AGENT_BENCH_OPENCLAW_THINKING")
        if thinking:
            argv.extend(["--thinking", thinking])
        return _run_cli(argv, self.timeout_seconds, self._run_command)

    def metadata(self, model: str) -> dict[str, Any]:
        return {
            "adapter": self.runtime,
            "model": model,
            "openclaw_version": command_output([self.binary, "--version"]),
            "openclaw_mode": "agent --local --json",
            "native_platform_tool_score": True,
        }


class HermesNativeBackend:
    runtime = HERMES_NATIVE

    def __init__(
        self,
        *,
        binary: str | None = None,
        toolsets: str | None = None,
        timeout_seconds: int = 600,
        run_command: CommandRunner | None = None,
    ) -> None:
        self.binary = binary or os.environ.get("LOCAL_AGENT_BENCH_HERMES_BIN", "hermes")
        self.toolsets = toolsets or os.environ.get("LOCAL_AGENT_BENCH_HERMES_NATIVE_TOOLSETS", "safe")
        self.timeout_seconds = timeout_seconds
        self._run_command = run_command or run_subprocess

    def native_turn(self, model: str, prompt: str) -> CommandResult:
        argv = [
            self.binary,
            "chat",
            "--query",
            prompt,
            "--quiet",
            "--model",
            model,
            "--toolsets",
            self.toolsets,
            "--source",
            "local-agent-bench-native",
        ]
        return _run_cli(argv, self.timeout_seconds, self._run_command)

    def metadata(self, model: str) -> dict[str, Any]:
        return {
            "adapter": self.runtime,
            "model": model,
            "hermes_version": command_output([self.binary, "--version"]),
            "hermes_mode": "chat --query --quiet",
            "hermes_toolsets": self.toolsets,
            "native_platform_tool_score": True,
        }


def normalize_runtime(runtime: str) -> str:
    normalized = RUNTIME_ALIASES.get(runtime)
    if not normalized:
        valid = ", ".join(sorted(RUNTIME_ALIASES))
        raise ValueError(f"unknown runtime: {runtime}. Expected one of: {valid}")
    return normalized


def build_backend(runtime: str, base_url: str, timeout_seconds: int = 600) -> ChatBackend:
    normalized = normalize_runtime(runtime)
    if normalized == RAW_OLLAMA_REACT:
        return OllamaChatBackend(base_url)
    if normalized == OPENCLAW_REACT:
        return OpenClawChatBackend(timeout_seconds=timeout_seconds)
    if normalized == HERMES_REACT:
        return HermesChatBackend(timeout_seconds=timeout_seconds)
    if normalized == OPENCLAW_NATIVE:
        return OpenClawNativeBackend(timeout_seconds=timeout_seconds)
    if normalized == HERMES_NATIVE:
        return HermesNativeBackend(timeout_seconds=timeout_seconds)
    raise AssertionError(f"unhandled runtime: {normalized}")


def render_cli_turn_prompt(messages: list[dict[str, str]]) -> str:
    rendered = [
        "You are the assistant in a local benchmark ReAct loop.",
        "Return only the next assistant message. Do not wrap it in Markdown.",
        "If a tool is needed, emit the benchmark Action / Action Input format exactly.",
        "",
        "Conversation so far:",
    ]
    labels = {"system": "System", "user": "User", "assistant": "Assistant"}
    for message in messages:
        role = labels.get(message["role"], message["role"].title())
        rendered.append(f"{role}:\n{message['content']}")
    rendered.append("")
    rendered.append("Next assistant message:")
    return "\n\n".join(rendered)


def extract_openclaw_response_text(stdout: str) -> str:
    data = _parse_json_object(stdout)
    if data is None:
        return stdout.strip()

    candidates = [
        data.get("replyText"),
        data.get("finalText"),
        data.get("text"),
        data.get("message"),
        _nested(data, ["meta", "finalAssistantVisibleText"]),
        _nested(data, ["result", "replyText"]),
        _nested(data, ["result", "finalText"]),
        _nested(data, ["result", "text"]),
        _nested(data, ["result", "message"]),
        _nested(data, ["result", "meta", "finalAssistantVisibleText"]),
    ]
    payload_text = _payloads_text(data.get("payloads")) or _payloads_text(_nested(data, ["result", "payloads"]))
    output_text = _payloads_text(data.get("outputs")) or _payloads_text(_nested(data, ["result", "outputs"]))
    if payload_text:
        candidates.append(payload_text)
    if output_text:
        candidates.append(output_text)

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return stdout.strip()


def run_subprocess(argv: list[str], timeout_seconds: int, cwd: Path) -> CommandResult:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise BackendError(f"runtime command not found: {argv[0]}", "RUNTIME_UNAVAILABLE") from exc
    except subprocess.TimeoutExpired as exc:
        raise BackendError(f"runtime timed out after {timeout_seconds}s: {argv[0]}", "TIMEOUT") from exc
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def command_output(argv: list[str]) -> str | None:
    if shutil.which(argv[0]) is None:
        return None
    try:
        completed = subprocess.run(argv, check=False, text=True, capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    text = completed.stdout.strip() or completed.stderr.strip()
    return redact_command_text(text)


def redact_command_text(text: str) -> str:
    home = str(Path.home())
    redacted = text.replace(str(PROJECT_ROOT), "<PROJECT_ROOT>")
    if home:
        redacted = redacted.replace(home, "<HOME>")
    return redacted


def _run_cli(argv: list[str], timeout_seconds: int, run_command: CommandRunner) -> CommandResult:
    result = run_command(argv, timeout_seconds, PROJECT_ROOT)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or f"{argv[0]} exited with {result.returncode}"
        raise BackendError(detail, "RUNTIME_ERROR")
    return result


def _model_info(client: OllamaClient, model: str) -> dict[str, Any]:
    try:
        return client.show_model(model)
    except OllamaError as exc:
        return {"error": str(exc)}


def _ollama_failure_reason(exc: OllamaError) -> str:
    text = f"{exc} {exc.body or ''}".casefold()
    if "model" in text and "not found" in text:
        return "MODEL_NOT_INSTALLED"
    if exc.status_code == 404:
        return "MODEL_NOT_INSTALLED"
    return "OLLAMA_UNREACHABLE"


def _parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _nested(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _payloads_text(payloads: Any) -> str | None:
    if not isinstance(payloads, list):
        return None
    parts = [payload.get("text", "") for payload in payloads if isinstance(payload, dict)]
    text = "\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    return text or None
