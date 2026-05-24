from __future__ import annotations

import platform
import subprocess
from typing import Any


def collect_run_metadata(
    model: str,
    runtime: str,
    benchmark: str,
    adapter_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "runtime": runtime,
        "benchmark": benchmark,
        "git_commit": _command(["git", "rev-parse", "HEAD"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "model": model,
    }
    if adapter_metadata:
        metadata.update(adapter_metadata)
    return metadata


def _command(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(args, check=False, text=True, capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or completed.stderr.strip()
