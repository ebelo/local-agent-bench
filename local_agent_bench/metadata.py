from __future__ import annotations

import platform
import subprocess
from typing import Any

from local_agent_bench.ollama import OllamaClient, OllamaError


def collect_run_metadata(client: OllamaClient, model: str, runtime: str, benchmark: str) -> dict[str, Any]:
    model_info = _model_info(client, model)
    return {
        "runtime": runtime,
        "benchmark": benchmark,
        "git_commit": _command(["git", "rev-parse", "HEAD"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ollama_version": _command(["ollama", "--version"]),
        "model": model,
        "model_details": model_info.get("details", {}),
        "model_info": model_info.get("model_info", {}),
    }


def _model_info(client: OllamaClient, model: str) -> dict[str, Any]:
    try:
        return client.show_model(model)
    except OllamaError as exc:
        return {"error": str(exc)}


def _command(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(args, check=False, text=True, capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or completed.stderr.strip()
