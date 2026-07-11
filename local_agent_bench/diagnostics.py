from __future__ import annotations

import os
import platform
import shlex
import shutil
from dataclasses import dataclass

from local_agent_bench.backends import (
    HERMES_NATIVE,
    HERMES_REACT,
    OPENCLAW_NATIVE,
    OPENCLAW_REACT,
    PI_NATIVE,
    PI_REACT,
    RAW_OLLAMA_REACT,
    command_output,
    normalize_runtime,
)
from local_agent_bench.ollama import OllamaClient, OllamaError
from local_agent_bench.tools import (
    ToolError,
    fetch_weather,
    get_weather,
    list_directory,
    read_file,
    resolve_location,
)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    layer: str
    detail: str


def run_diagnostics(
    base_url: str,
    model: str | None,
    requires_network: bool = True,
    runtime: str = RAW_OLLAMA_REACT,
) -> list[Check]:
    normalized_runtime = normalize_runtime(runtime)
    checks = [
        Check("python", True, "host", platform.python_version()),
        Check("platform", True, "host", platform.platform()),
        _filesystem_tools(),
        _known_location_fallback(),
    ]
    checks.extend(_runtime_checks(normalized_runtime, base_url, model))
    if requires_network:
        checks.extend([_weather_api(), _weather_tool()])
    return checks


def _runtime_checks(runtime: str, base_url: str, model: str | None) -> list[Check]:
    if runtime == RAW_OLLAMA_REACT:
        checks = [_ollama_api_version(base_url), _ollama_reachable(base_url)]
        if model:
            checks.append(_model_installed(base_url, model))
        return checks
    if runtime in {OPENCLAW_REACT, OPENCLAW_NATIVE}:
        return [_cli_available("openclaw", "LOCAL_AGENT_BENCH_OPENCLAW_BIN")]
    if runtime in {HERMES_REACT, HERMES_NATIVE}:
        return [_cli_available("hermes", "LOCAL_AGENT_BENCH_HERMES_BIN")]
    if runtime in {PI_REACT, PI_NATIVE}:
        return [_command_available("pi_cli", os.environ.get("LOCAL_AGENT_BENCH_PI_COMMAND", "pi"))]
    return [Check("runtime", False, "configuration", f"unsupported runtime: {runtime}")]


def _cli_available(default_binary: str, env_var: str) -> Check:
    binary = os.environ.get(env_var, default_binary)
    resolved = shutil.which(binary)
    if not resolved:
        return Check(f"{default_binary}_cli", False, "configuration", f"{binary} not found on PATH")
    version = command_output([binary, "--version"])
    return Check(f"{default_binary}_cli", version is not None, "configuration", version or f"{binary} exists")


def _command_available(name: str, command: str) -> Check:
    argv = shlex.split(command)
    if not argv:
        return Check(name, False, "configuration", "empty command")
    resolved = shutil.which(argv[0])
    if not resolved:
        return Check(name, False, "configuration", f"{argv[0]} not found on PATH")
    version = command_output([*argv, "--version"])
    return Check(name, version is not None, "configuration", version or f"{command} exists")


def _ollama_api_version(base_url: str) -> Check:
    client = OllamaClient(base_url)
    try:
        version = client.version()
    except OllamaError as exc:
        return Check("ollama_api_version", False, "configuration", f"{base_url}: {exc}")
    return Check("ollama_api_version", True, "configuration", version)



def _ollama_reachable(base_url: str) -> Check:
    client = OllamaClient(base_url)
    try:
        models = client.list_models()
    except OllamaError as exc:
        return Check("ollama_api", False, "configuration", f"{base_url}: {exc}")
    return Check("ollama_api", True, "configuration", f"{base_url}, models={len(models)}")


def _model_installed(base_url: str, model: str) -> Check:
    client = OllamaClient(base_url)
    try:
        models = client.list_models()
    except OllamaError as exc:
        return Check("model_installed", False, "configuration", str(exc))
    if model in models:
        return Check("model_installed", True, "configuration", model)
    return Check("model_installed", False, "configuration", f"{model} not in {models}")


def _filesystem_tools() -> Check:
    try:
        listing = list_directory(".")
        fixture = read_file("benchmarks/fixtures.md")
    except ToolError as exc:
        return Check("filesystem_tools", False, "tooling", str(exc))
    except Exception as exc:
        return Check("filesystem_tools", False, "tooling", f"{type(exc).__name__}: {exc}")
    entries = len(listing["entries"])
    return Check("filesystem_tools", True, "tooling", f"entries={entries}; fixture={len(fixture['content'])} chars")


def _known_location_fallback() -> Check:
    try:
        location = resolve_location("Berlin, Germany")
    except Exception as exc:
        return Check("known_location_fallback", False, "tooling", f"{type(exc).__name__}: {exc}")
    detail = f"{location['name']} ({location['latitude']}, {location['longitude']})"
    return Check("known_location_fallback", True, "tooling", detail)


def _weather_api() -> Check:
    try:
        weather = fetch_weather(52.52, 13.405)
    except Exception as exc:
        return Check("weather_api", False, "network", f"{type(exc).__name__}: {exc}")
    current = weather.get("current", {})
    return Check("weather_api", "temperature_2m" in current, "network", f"current keys={sorted(current)}")


def _weather_tool() -> Check:
    try:
        weather = get_weather("Berlin, Germany")
    except Exception as exc:
        return Check("weather_tool", False, "tooling", f"{type(exc).__name__}: {exc}")
    return Check("weather_tool", True, "tooling", f"{weather['location']}; weather={weather['temperature_c']} C")
