from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from local_agent_bench.backends import HERMES_NATIVE, OPENCLAW_NATIVE, PI_NATIVE, RAW_OLLAMA_REACT, build_backend, normalize_runtime
from local_agent_bench.diagnostics import run_diagnostics
from local_agent_bench.judge import judge_native_result
from local_agent_bench.metadata import collect_run_metadata
from local_agent_bench.native import run_native_task
from local_agent_bench.react import result_to_jsonable, run_task
from local_agent_bench.redaction import redact_local_context
from local_agent_bench.tasks import load_tasks


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = PROJECT_ROOT / "benchmarks" / "smoke.json"


def main() -> int:
    parser = argparse.ArgumentParser(prog="local-agent-bench")
    parser.add_argument("--ollama-base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    parser.add_argument("--runtime", default=os.environ.get("LOCAL_AGENT_BENCH_RUNTIME", RAW_OLLAMA_REACT))
    parser.add_argument(
        "--runtime-timeout",
        type=int,
        default=int(os.environ.get("LOCAL_AGENT_BENCH_RUNTIME_TIMEOUT", "600")),
        help="Timeout in seconds for CLI-backed runtimes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    diagnose = subparsers.add_parser("diagnose", help="Check local configuration and tool availability.")
    diagnose.add_argument("--model", default=os.environ.get("OLLAMA_MODEL"))
    diagnose.add_argument("--runtime", dest="command_runtime", default=None)

    run = subparsers.add_parser("run", help="Run benchmark tasks.")
    run.add_argument("--model", default=os.environ.get("OLLAMA_MODEL"), required=os.environ.get("OLLAMA_MODEL") is None)
    run.add_argument("--runtime", dest="command_runtime", default=None)
    run.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    run.add_argument("--output", type=Path)
    run.add_argument("--max-steps", type=int, default=5)
    run.add_argument("--runtime-timeout", dest="command_runtime_timeout", type=int, default=None)
    run.add_argument("--skip-preflight", action="store_true")
    run.add_argument(
        "--task-timeout",
        type=float,
        default=float(os.environ.get("LOCAL_AGENT_BENCH_TASK_TIMEOUT", "0")),
        help="Per-task timeout in seconds. Tasks exceeding this are auto-failed with TIMEOUT. 0 = disabled.",
    )

    rejudge = subparsers.add_parser("rejudge", help="Re-score native adapter results with an LLM judge.")
    rejudge.add_argument("input", type=Path, help="JSON result file to re-score.")
    rejudge.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    rejudge.add_argument("--output", type=Path, help="Output file (default: overwrite input).")
    rejudge.add_argument("--judge-model", default=os.environ.get("LOCAL_AGENT_BENCH_JUDGE_MODEL", "ollama/glm-5.2:cloud"))
    rejudge.add_argument("--timeout", type=int, default=60)


    args = parser.parse_args()
    if args.command == "rejudge":
        return _rejudge(args.input, args.benchmark, args.output, args.judge_model, args.timeout)
    try:
        runtime = normalize_runtime(args.command_runtime or args.runtime)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.command == "diagnose":
        return _diagnose(args.ollama_base_url, args.model, runtime)
    if args.command == "run":
        return _run(
            args.ollama_base_url,
            runtime,
            args.model,
            args.benchmark,
            args.output,
            args.max_steps,
            args.skip_preflight,
            args.command_runtime_timeout if args.command_runtime_timeout is not None else args.runtime_timeout,
            args.task_timeout,
        )
    return 2


def _diagnose(base_url: str, model: str | None, runtime: str, requires_network: bool = True) -> int:
    checks = run_diagnostics(base_url, model, requires_network=requires_network, runtime=runtime)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"{status} [{check.layer}] {check.name}: {check.detail}")
    return 0 if all(check.ok for check in checks) else 1


def _run(
    base_url: str,
    runtime: str,
    model: str,
    benchmark: Path,
    output: Path | None,
    max_steps: int,
    skip_preflight: bool,
    runtime_timeout: int,
    task_timeout: float = 0.0,
) -> int:
    backend = build_backend(runtime, base_url, timeout_seconds=runtime_timeout)
    tasks = load_tasks(benchmark)
    requires_network = any(task.requires_network for task in tasks)

    if not skip_preflight:
        checks = run_diagnostics(base_url, model, requires_network=requires_network, runtime=backend.runtime)
        failed = [check for check in checks if not check.ok]
        if failed:
            for check in checks:
                status = "PASS" if check.ok else "FAIL"
                print(f"{status} [{check.layer}] {check.name}: {check.detail}", file=sys.stderr)
            return 1

    if backend.runtime in {OPENCLAW_NATIVE, HERMES_NATIVE, PI_NATIVE}:
        results = [run_native_task(backend, model, task) for task in tasks]
    else:
        results = [run_task(backend, model, task, max_steps=max_steps, task_timeout=task_timeout) for task in tasks]
    jsonable = {
        "metadata": collect_run_metadata(model, backend.runtime, str(benchmark), backend.metadata(model)),
        "runtime": backend.runtime,
        "model": model,
        "benchmark": str(benchmark),
        "results": [result_to_jsonable(result) for result in results],
    }

    jsonable = redact_local_context(jsonable, PROJECT_ROOT)
    text = json.dumps(jsonable, indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    passed = sum(1 for result in results if result.score == 1.0)
    print(f"Summary: {passed}/{len(results)} passed", file=sys.stderr)
    return 0 if passed == len(results) else 1


def _rejudge(input_file: Path, benchmark: Path, output: Path | None, judge_model: str, timeout: int) -> int:
    """Re-score existing native adapter results with an LLM judge."""
    data = json.loads(input_file.read_text(encoding="utf-8"))
    tasks = {task.id: task for task in load_tasks(benchmark)}
    results = data.get("results", [])

    print(f"Re-judging {len(results)} results from {input_file} with {judge_model}...", file=sys.stderr)

    for i, result in enumerate(results):
        task_id = result.get("task_id", "")
        task = tasks.get(task_id)
        if not task:
            print(f"  [{i+1}/{len(results)}] SKIP - task '{task_id}' not found in benchmark", file=sys.stderr)
            continue

        final_answer = result.get("final_answer", "")
        if not final_answer or len(final_answer) < 10:
            result["judge"] = {
                "judge_score": 0.0,
                "judge_verdict": "JUDGE_FAIL",
                "judge_reasoning": "No meaningful response to evaluate.",
                "judge_model": judge_model,
            }
            print(f"  [{i+1}/{len(results)}] {task_id}: SKIP (empty response)", file=sys.stderr)
            continue

        # Skip if it's a runtime error with no model output
        reason = result.get("failure_reason", "")
        if reason == "RUNTIME_ERROR" and not any(c.isalpha() and c.islower() for c in final_answer[:200] if c.isalpha()):
            result["judge"] = {
                "judge_score": 0.0,
                "judge_verdict": "JUDGE_FAIL",
                "judge_reasoning": "Runtime error - no model output.",
                "judge_model": judge_model,
            }
            print(f"  [{i+1}/{len(results)}] {task_id}: SKIP (runtime error)", file=sys.stderr)
            continue

        verdict = judge_native_result(task, final_answer, judge_model=judge_model, timeout=timeout)
        result["judge"] = verdict
        score = verdict.get("judge_score", 0.0)
        v = verdict.get("judge_verdict", "?")
        reasoning = verdict.get("judge_reasoning", "")[:120]
        print(f"  [{i+1}/{len(results)}] {task_id}: {v} ({score:.2f}) - {reasoning}", file=sys.stderr)

    # Compute judge summary
    judge_scores = [r.get("judge", {}).get("judge_score", 0.0) for r in results]
    total = sum(judge_scores)
    print(f"Judge total: {total:.1f}/{len(results)} ", file=sys.stderr)

    # Update metadata
    data.setdefault("metadata", {})["judge_model"] = judge_model
    data["metadata"]["judge_total"] = total

    out_path = output or input_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Written to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
