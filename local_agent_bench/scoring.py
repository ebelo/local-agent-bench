from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from local_agent_bench.types import Task, ToolCall

PASS = "PASS"
NO_TOOL_ATTEMPT = "NO_TOOL_ATTEMPT"
INVALID_TOOL_SYNTAX = "INVALID_TOOL_SYNTAX"
WRONG_TOOL = "WRONG_TOOL"
BAD_ARGUMENTS = "BAD_ARGUMENTS"
TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
IGNORED_TOOL_RESULT = "IGNORED_TOOL_RESULT"
HALLUCINATED_RESULT = "HALLUCINATED_RESULT"
MISSING_REQUIRED_TOOL = "MISSING_REQUIRED_TOOL"
FORBIDDEN_TOOL = "FORBIDDEN_TOOL"
ASSERTION_FAILED = "ASSERTION_FAILED"
UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


def score_task(
    task: Task,
    final_answer: str,
    tool_calls: list[ToolCall],
    invalid_tool_syntax: bool,
) -> tuple[float, str, list[dict[str, Any]]]:
    called = [call.name for call in tool_calls]
    called_set = set(called)
    required = set(task.required_tools)
    assertion_results: list[dict[str, Any]] = []

    if invalid_tool_syntax:
        return 0.25, INVALID_TOOL_SYNTAX, assertion_results

    if required and not tool_calls:
        return 0.0, NO_TOOL_ATTEMPT, assertion_results

    forbidden = set(task.forbidden_tools).intersection(called_set)
    if forbidden:
        return 0.25, FORBIDDEN_TOOL, [{"ok": False, "type": "forbidden_tool", "detail": sorted(forbidden)}]

    if task.allowed_tools:
        unexpected = called_set.difference(task.allowed_tools)
        if unexpected:
            return 0.25, WRONG_TOOL, [{"ok": False, "type": "allowed_tools", "detail": sorted(unexpected)}]

    if required:
        missing = required.difference(called_set)
        if missing:
            score = 0.25 if called_set else 0.0
            return score, MISSING_REQUIRED_TOOL, [{"ok": False, "type": "required_tools", "detail": sorted(missing)}]

    if any(not call.ok for call in tool_calls) and not _expects_failed_tool_call(task.assertions):
        if any(call.error and "missing" in call.error.lower() for call in tool_calls):
            return 0.5, BAD_ARGUMENTS, assertion_results
        return 0.5, TOOL_EXECUTION_FAILED, assertion_results

    assertion_results = [_evaluate_assertion(assertion, final_answer, tool_calls) for assertion in task.assertions]
    if assertion_results and not all(result["ok"] for result in assertion_results):
        if any(_assertion_uses_tool(result) for result in assertion_results if not result["ok"]):
            return 0.75, IGNORED_TOOL_RESULT, assertion_results
        return 0.5, ASSERTION_FAILED, assertion_results

    if assertion_results or required:
        return 1.0, PASS, assertion_results

    return 0.0, HALLUCINATED_RESULT if final_answer else UNKNOWN_FAILURE, assertion_results


def _evaluate_assertion(assertion: dict[str, Any], final_answer: str, tool_calls: list[ToolCall]) -> dict[str, Any]:
    assertion_type = assertion.get("type")
    answer = final_answer.casefold()

    if assertion_type == "answer_contains":
        value = str(assertion.get("value", ""))
        return _result(assertion, _contains(answer, value), value)

    if assertion_type == "answer_contains_any":
        values = [str(value) for value in assertion.get("values", [])]
        matched = [value for value in values if _contains(answer, value)]
        return _result(assertion, bool(matched), {"matched": matched, "expected": values})

    if assertion_type == "answer_contains_all":
        values = [str(value) for value in assertion.get("values", [])]
        missing = [value for value in values if not _contains(answer, value)]
        return _result(assertion, not missing, {"missing": missing, "expected": values})

    if assertion_type == "answer_not_contains_any":
        values = [str(value) for value in assertion.get("values", [])]
        matched = [value for value in values if _contains(answer, value)]
        return _result(assertion, not matched, {"matched": matched, "forbidden": values})

    if assertion_type == "tool_call_count":
        tool = str(assertion.get("tool", ""))
        observed = sum(1 for call in tool_calls if call.name == tool)
        minimum = int(assertion.get("min", 0))
        maximum = assertion.get("max")
        ok = observed >= minimum and (maximum is None or observed <= int(maximum))
        return _result(assertion, ok, {"observed": observed, "min": minimum, "max": maximum})

    if assertion_type == "tool_call_sequence":
        expected = [str(tool) for tool in assertion.get("tools", [])]
        observed = [call.name for call in tool_calls]
        return _result(assertion, _contains_subsequence(observed, expected), {"observed": observed, "expected": expected})

    if assertion_type == "tool_call_failed":
        tool = str(assertion.get("tool", ""))
        failed = [call for call in tool_calls if call.name == tool and not call.ok]
        return _result(
            assertion,
            bool(failed),
            {"observed": [{"name": call.name, "args": call.args, "error": call.error} for call in failed]},
        )

    if assertion_type == "tool_result_contains":
        values = _tool_values(tool_calls, str(assertion.get("tool", "")), str(assertion.get("path", "")))
        expected = assertion.get("value")
        ok = any(_same_value(value, expected) for value in values)
        return _result(assertion, ok, {"observed": values, "expected": expected})

    if assertion_type == "answer_contains_tool_result":
        values = _tool_values(tool_calls, str(assertion.get("tool", "")), str(assertion.get("path", "")))
        matched = [value for value in values if _answer_contains_value(answer, value)]
        return _result(assertion, bool(matched), {"matched": matched, "observed": values})

    return _result(assertion, False, f"unknown assertion type: {assertion_type}")


def _assertion_uses_tool(result: dict[str, Any]) -> bool:
    assertion = result.get("assertion", {})
    assertion_type = assertion.get("type") if isinstance(assertion, dict) else None
    return assertion_type in {"tool_result_contains", "answer_contains_tool_result"}


def _expects_failed_tool_call(assertions: list[dict[str, Any]]) -> bool:
    return any(assertion.get("type") == "tool_call_failed" for assertion in assertions)


def _contains(answer: str, value: str) -> bool:
    return value.casefold() in answer


def _contains_subsequence(observed: list[str], expected: list[str]) -> bool:
    if not expected:
        return True
    index = 0
    for tool in observed:
        if tool == expected[index]:
            index += 1
            if index == len(expected):
                return True
    return False


def _answer_contains_value(answer: str, value: Any) -> bool:
    if isinstance(value, (int, float)):
        number = float(value)
        variants = {f"{number:.1f}", str(value)}
        if number.is_integer():
            variants.add(str(int(number)))
        return any(re.search(rf"(?<![\d.]){re.escape(variant)}(?![\d.])", answer) for variant in variants)
    return _contains(answer, str(value))


def _result(assertion: dict[str, Any], ok: bool, detail: Any) -> dict[str, Any]:
    return {"ok": ok, "type": assertion.get("type"), "assertion": assertion, "detail": detail}


def _tool_values(tool_calls: list[ToolCall], tool: str, path: str) -> list[Any]:
    values: list[Any] = []
    for call in tool_calls:
        if call.name != tool or not call.ok:
            continue
        values.extend(_extract_path(call.result, path))
    return values


def _extract_path(value: Any, path: str) -> list[Any]:
    if not path:
        return [value]

    current = [value]
    for part in path.split("."):
        expand_list = part.endswith("[]")
        key = part[:-2] if expand_list else part
        next_values: list[Any] = []
        for item in current:
            if key:
                if not isinstance(item, dict) or key not in item:
                    continue
                value_at_key = item[key]
            else:
                value_at_key = item

            if expand_list and isinstance(value_at_key, list):
                next_values.extend(value_at_key)
            else:
                next_values.append(value_at_key)
        current = next_values
    return list(_flatten(current))


def _flatten(values: Iterable[Any]) -> Iterable[Any]:
    for value in values:
        if isinstance(value, list):
            yield from _flatten(value)
        else:
            yield value


def _same_value(observed: Any, expected: Any) -> bool:
    if isinstance(observed, (int, float)) and isinstance(expected, (int, float)):
        return float(observed) == float(expected)
    return str(observed).casefold() == str(expected).casefold()
