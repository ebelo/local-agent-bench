from __future__ import annotations

import json
import re
import time
from dataclasses import asdict

from local_agent_bench.backends import BackendError, ChatBackend, _ollama_failure_reason
from local_agent_bench.scoring import score_task
from local_agent_bench.tools import ToolError, call_tool, tool_descriptions
from local_agent_bench.types import Task, TaskResult, ToolCall

ACTION_NAME_RE = re.compile(r"Action:\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
ACTION_INPUT_RE = re.compile(r"Action Input:\s*", re.IGNORECASE)
FINAL_RE = re.compile(r"Final Answer:\s*(?P<answer>.*)", re.DOTALL | re.IGNORECASE)


SYSTEM_PROMPT = """You are running inside a benchmark harness.

Use tools when the task requires live data or filesystem access.

Available tools:
{tools}

Use exactly one of these formats:

Thought: brief reasoning
Action: tool_name
Action Input: {{"argument": "value"}}

or:

Final Answer: concise answer to the user

Do not invent filesystem contents or current weather. If a tool is needed, call it.
"""


def run_task(backend: ChatBackend, model: str, task: Task, max_steps: int = 5) -> TaskResult:
    start = time.monotonic()
    transcript = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools=tool_descriptions())},
        {"role": "user", "content": task.prompt},
    ]
    calls: list[ToolCall] = []
    invalid_tool_syntax = False
    final_answer = ""

    for _ in range(max_steps):
        try:
            content = backend.chat(model, transcript)
        except BackendError as exc:
            return TaskResult(
                task_id=task.id,
                category=task.category,
                runtime=backend.runtime,
                model=model,
                score=0.0,
                failure_reason=exc.failure_reason,
                final_answer=str(exc),
                tool_calls=calls,
                latency_ms=_elapsed_ms(start),
                raw_transcript=transcript,
                assertion_results=[],
            )

        transcript.append({"role": "assistant", "content": content})
        final_match = FINAL_RE.search(content)
        if final_match:
            final_answer = final_match.group("answer").strip()
            break

        try:
            name, args = parse_action(content)
        except ValueError:
            final_answer = content.strip()
            if calls:
                break
            invalid_tool_syntax = True
            break

        try:
            result = call_tool(name, args)
            calls.append(ToolCall(name=name, args=args, ok=True, result=result))
            observation = json.dumps(result, ensure_ascii=False)
        except (TypeError, ToolError) as exc:
            calls.append(ToolCall(name=name, args=args, ok=False, error=str(exc)))
            observation = json.dumps({"error": str(exc)}, ensure_ascii=False)

        transcript.append({"role": "user", "content": f"Observation: {observation}"})
    else:
        final_answer = "Task did not finish within max_steps."

    score, reason, assertion_results = score_task(task, final_answer, calls, invalid_tool_syntax)
    return TaskResult(
        task_id=task.id,
        category=task.category,
        runtime=backend.runtime,
        model=model,
        score=score,
        failure_reason=reason,
        final_answer=final_answer,
        tool_calls=calls,
        latency_ms=_elapsed_ms(start),
        raw_transcript=transcript,
        assertion_results=assertion_results,
    )


def result_to_jsonable(result: TaskResult) -> dict[str, object]:
    data = asdict(result)
    return data


def parse_action(content: str) -> tuple[str, dict[str, object]]:
    name_match = ACTION_NAME_RE.search(content)
    input_match = ACTION_INPUT_RE.search(content)
    if not name_match or not input_match:
        raise ValueError("missing Action or Action Input")

    payload = content[input_match.end() :].lstrip()
    if not payload.startswith("{"):
        raise ValueError("Action Input must start with a JSON object")

    try:
        args, _ = json.JSONDecoder().raw_decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc

    if not isinstance(args, dict):
        raise ValueError("Action Input must be a JSON object")
    return name_match.group("name"), args


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
