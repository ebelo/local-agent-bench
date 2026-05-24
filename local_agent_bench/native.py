from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from typing import Any, Protocol

from local_agent_bench.backends import BackendError, CommandResult
from local_agent_bench.types import Task, TaskResult, ToolCall


NATIVE_PASS = "PASS"
NATIVE_NO_TOOL_ATTEMPT = "NO_NATIVE_TOOL_ATTEMPT"
NATIVE_MISSING_REQUIRED_TOOL = "NATIVE_MISSING_REQUIRED_TOOL"
NATIVE_MISSING_REQUIRED_ARGUMENT = "NATIVE_MISSING_REQUIRED_ARGUMENT"
NATIVE_WRONG_TOOL = "NATIVE_WRONG_TOOL"


TOOL_ALIASES = {
    "cwd": "get_cwd",
    "getcwd": "get_cwd",
    "get_cwd": "get_cwd",
    "list": "list_directory",
    "listfiles": "list_directory",
    "listdirectory": "list_directory",
    "list_directory": "list_directory",
    "read": "read_file",
    "readfile": "read_file",
    "read_file": "read_file",
    "weather": "get_weather",
    "getweather": "get_weather",
    "get_weather": "get_weather",
}

REQUIRED_ARGUMENT_SETS = {
    "get_cwd": [set()],
    "list_directory": [{"path"}],
    "read_file": [{"path"}],
    "get_weather": [{"location"}, {"latitude", "longitude"}],
}

class NativePlatformBackend(Protocol):
    runtime: str

    def native_turn(self, model: str, prompt: str) -> CommandResult:
        ...

    def metadata(self, model: str) -> dict[str, Any]:
        ...


def run_native_task(backend: NativePlatformBackend, model: str, task: Task) -> TaskResult:
    start = time.monotonic()
    transcript = [{"role": "user", "content": task.prompt}]
    try:
        turn = backend.native_turn(model, task.prompt)
    except BackendError as exc:
        return TaskResult(
            task_id=task.id,
            category=task.category,
            runtime=backend.runtime,
            model=model,
            score=0.0,
            failure_reason=exc.failure_reason,
            final_answer=str(exc),
            tool_calls=[],
            latency_ms=_elapsed_ms(start),
            raw_transcript=transcript,
            native_platform_tool_score=None,
        )

    final_answer = (turn.stdout.strip() or turn.stderr.strip()).strip()
    transcript.append({"role": "assistant", "content": final_answer})
    calls = extract_native_tool_calls(final_answer)
    native_score = score_native_platform_tools(task, calls)
    return TaskResult(
        task_id=task.id,
        category=task.category,
        runtime=backend.runtime,
        model=model,
        score=float(native_score["score"]),
        failure_reason=str(native_score["failure_reason"]),
        final_answer=final_answer,
        tool_calls=calls,
        latency_ms=_elapsed_ms(start),
        raw_transcript=transcript,
        assertion_results=[],
        native_platform_tool_score=native_score,
    )


def score_native_platform_tools(task: Task, calls: list[ToolCall]) -> dict[str, Any]:
    required = [_canonical_tool(tool) for tool in task.required_tools]
    observed = [_canonical_tool(call.name) for call in calls]
    observed_set = set(observed)
    required_set = set(required)

    if not required_set:
        return _native_result(1.0, NATIVE_PASS, calls, [])
    if not calls:
        return _native_result(0.0, NATIVE_NO_TOOL_ATTEMPT, calls, sorted(required_set))

    missing_tools = sorted(required_set.difference(observed_set))
    if missing_tools:
        score = 0.25 if observed_set else 0.0
        return _native_result(score, NATIVE_MISSING_REQUIRED_TOOL, calls, missing_tools)

    bad_arguments = []
    for call in calls:
        name = _canonical_tool(call.name)
        if name not in required_set:
            continue
        missing = _missing_arguments(name, call.args)
        if missing:
            bad_arguments.append({"tool": name, "missing": missing, "args": call.args})

    if bad_arguments:
        return _native_result(
            0.5,
            NATIVE_MISSING_REQUIRED_ARGUMENT,
            calls,
            [],
            missing_required_arguments=bad_arguments,
        )

    allowed = {_canonical_tool(tool) for tool in task.allowed_tools} if task.allowed_tools else required_set
    unexpected = sorted(observed_set.difference(allowed))
    if task.allowed_tools and unexpected:
        return _native_result(0.25, NATIVE_WRONG_TOOL, calls, [], unexpected_tools=unexpected)

    return _native_result(1.0, NATIVE_PASS, calls, [])


def extract_native_tool_calls(text: str) -> list[ToolCall]:
    calls: list[ToolCall] = []
    seen: set[tuple[str, str, bool, str | None]] = set()
    for item in _json_objects(text):
        call = _tool_call_from_object(item)
        if call is not None:
            key = (call.name, json.dumps(call.args, sort_keys=True, default=str), call.ok, call.error)
            if key in seen:
                continue
            seen.add(key)
            calls.append(call)
    return calls


def native_result_to_jsonable(result: TaskResult) -> dict[str, object]:
    return asdict(result)


def _tool_call_from_object(item: Any) -> ToolCall | None:
    if not isinstance(item, dict):
        return None
    if item.get("name") == "tool_call":
        if "arguments" not in item:
            return None
        arguments = item.get("arguments")
        if not isinstance(arguments, dict):
            return ToolCall(name="tool_call", args={}, ok=False, error="arguments must be an object")
        tool_name = str(arguments.get("tool") or arguments.get("name") or arguments.get("id") or "tool_call")
        args = {key: value for key, value in arguments.items() if key not in {"tool", "name", "id"}}
        return ToolCall(name=_canonical_tool(tool_name), args=args, ok=not _missing_arguments(_canonical_tool(tool_name), args))
    if "tool" in item or "tool_name" in item:
        tool_name = str(item.get("tool") or item.get("tool_name"))
        args = item.get("arguments") or item.get("args") or {}
        args = args if isinstance(args, dict) else {}
        return ToolCall(name=_canonical_tool(tool_name), args=args, ok=not _missing_arguments(_canonical_tool(tool_name), args))
    return None


def _json_objects(text: str) -> list[Any]:
    parsed = _parse_json(text)
    if parsed is not None:
        if isinstance(parsed, str):
            return []
        return _flatten_json(parsed)

    objects = []
    decoder = json.JSONDecoder()
    for start in [match.start() for match in re.finditer(r"\{", text)]:
        try:
            item, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        objects.append(item)
    return objects


def _flatten_json(item: Any) -> list[Any]:
    if isinstance(item, dict):
        values = [item]
        for value in item.values():
            values.extend(_flatten_json(value))
        return values
    if isinstance(item, list):
        values = []
        for value in item:
            values.extend(_flatten_json(value))
        return values
    if isinstance(item, str):
        return _json_objects(item)
    return []


def _parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _canonical_tool(name: str) -> str:
    key = re.sub(r"[^a-z0-9_]", "", name.casefold())
    return TOOL_ALIASES.get(key, key)


def _missing_arguments(tool: str, args: dict[str, Any]) -> list[str]:
    alternatives = REQUIRED_ARGUMENT_SETS.get(tool)
    if alternatives is None:
        return []
    present = {key for key, value in args.items() if value is not None and value != ""}
    if any(required.issubset(present) for required in alternatives):
        return []
    best = min(alternatives, key=lambda required: len(required.difference(present)))
    return sorted(best.difference(present))


def _native_result(
    score: float,
    failure_reason: str,
    calls: list[ToolCall],
    missing_required_tools: list[str],
    **extra: Any,
) -> dict[str, Any]:
    result = {
        "score": score,
        "failure_reason": failure_reason,
        "tool_intent_detected": bool(calls),
        "observed_tool_calls": [{"name": call.name, "args": call.args, "ok": call.ok, "error": call.error} for call in calls],
        "missing_required_tools": missing_required_tools,
    }
    result.update(extra)
    return result


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
