from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from local_agent_bench.backends import BackendError
from local_agent_bench.judge import judge_native_result
from local_agent_bench.native import NativePlatformBackend
from local_agent_bench.scoring import PASS, score_task
from local_agent_bench.types import Task, TaskResult


PLATFORM_NATIVE_PASS = "PLATFORM_NATIVE_PASS"
PLATFORM_NATIVE_PARTIAL = "PLATFORM_NATIVE_PARTIAL"
PLATFORM_NATIVE_FAIL = "PLATFORM_NATIVE_FAIL"
PLATFORM_NATIVE_JUDGE_ERROR = "PLATFORM_NATIVE_JUDGE_ERROR"


def run_platform_native_task(
    backend: NativePlatformBackend,
    model: str,
    task: Task,
    *,
    judge_model: str | None = None,
    judge_timeout: int = 60,
) -> TaskResult:
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
            assertion_results=[],
            native_platform_tool_score={
                "suite": "platform-native",
                "score": 0.0,
                "failure_reason": PLATFORM_NATIVE_FAIL,
                "judge": {
                    "judge_score": 0.0,
                    "judge_verdict": "JUDGE_FAIL",
                    "judge_reasoning": f"Runtime error: {exc}",
                    "judge_model": judge_model,
                },
                "deterministic_score": 0.0,
                "deterministic_reason": "RUNTIME_ERROR",
                "deterministic_passed": False,
                "assertion_results": [],
            },
        )

    final_answer = (turn.stdout.strip() or turn.stderr.strip()).strip()
    transcript.append({"role": "assistant", "content": final_answer})

    blocked_reason = _blocked_platform_reason(final_answer)
    if blocked_reason:
        platform_score = {
            "suite": "platform-native",
            "score": 0.0,
            "failure_reason": PLATFORM_NATIVE_FAIL,
            "judge": {
                "judge_score": 0.0,
                "judge_verdict": "JUDGE_FAIL",
                "judge_reasoning": blocked_reason,
                "judge_model": judge_model,
            },
            "deterministic_score": 0.0,
            "deterministic_reason": blocked_reason,
            "deterministic_passed": False,
            "assertion_results": [],
        }
        return TaskResult(
            task_id=task.id,
            category=task.category,
            runtime=backend.runtime,
            model=model,
            score=0.0,
            failure_reason=PLATFORM_NATIVE_FAIL,
            final_answer=final_answer,
            tool_calls=[],
            latency_ms=_elapsed_ms(start),
            raw_transcript=transcript,
            assertion_results=[],
            native_platform_tool_score=platform_score,
        )

    deterministic_score, deterministic_reason, assertion_results = score_task(task, final_answer, [], False)
    judge = judge_native_result(
        task,
        final_answer,
        transcript=transcript,
        judge_model=judge_model,
        timeout=judge_timeout,
    )
    judge_score = float(judge.get("judge_score", 0.0) or 0.0)
    judge_verdict = str(judge.get("judge_verdict", PLATFORM_NATIVE_JUDGE_ERROR))
    reason = _platform_native_reason(judge_score, judge_verdict)

    # Keep deterministic assertions as guardrails but use the judge as the
    # primary score: native platform outputs vary too much for tool-name scoring.
    platform_score: dict[str, Any] = {
        "suite": "platform-native",
        "score": judge_score,
        "failure_reason": reason,
        "judge": judge,
        "deterministic_score": deterministic_score,
        "deterministic_reason": deterministic_reason,
        "deterministic_passed": deterministic_reason == PASS,
        "assertion_results": assertion_results,
    }

    return TaskResult(
        task_id=task.id,
        category=task.category,
        runtime=backend.runtime,
        model=model,
        score=judge_score,
        failure_reason=reason,
        final_answer=final_answer,
        tool_calls=[],
        latency_ms=_elapsed_ms(start),
        raw_transcript=transcript,
        assertion_results=assertion_results,
        native_platform_tool_score=platform_score,
    )


def platform_native_result_to_jsonable(result: TaskResult) -> dict[str, object]:
    return asdict(result)


def _platform_native_reason(score: float, judge_verdict: str) -> str:
    if score >= 0.9:
        return PLATFORM_NATIVE_PASS
    if score > 0.0:
        return PLATFORM_NATIVE_PARTIAL
    if judge_verdict == "JUDGE_ERROR":
        return PLATFORM_NATIVE_JUDGE_ERROR
    return PLATFORM_NATIVE_FAIL


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _blocked_platform_reason(final_answer: str) -> str | None:
    text = final_answer.casefold().strip()
    if not text:
        return "No platform output."
    if "context overflow" in text or "prompt too large" in text:
        return "Platform blocked the task before model execution: context overflow."
    if "model override" in text and "not allowed" in text:
        return "Platform blocked the task before model execution: model override not allowed."
    if text.startswith("session_id:") and len(text.splitlines()) == 1:
        return "Platform produced only a session id and no model answer."
    return None
