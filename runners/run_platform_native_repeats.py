#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NATIVE_RUNTIMES = {"openclaw-native", "hermes-native", "pi-native"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run independent repeated platform-native trials and summarize variance.",
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--runtime", default="pi-native", choices=sorted(NATIVE_RUNTIMES))
    parser.add_argument("--benchmark", type=Path, default=PROJECT_ROOT / "benchmarks" / "platform_native.json")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--results-dir", type=Path, default=PROJECT_ROOT / "results")
    parser.add_argument("--runtime-timeout", type=int, default=300)
    parser.add_argument("--judge-timeout", type=int, default=120)
    parser.add_argument("--judge-model", default=os.environ.get("LOCAL_AGENT_BENCH_JUDGE_MODEL", "ollama/glm-5.2:cloud"))
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--label", help="Optional label for output filenames.")
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be >= 1")

    env = os.environ.copy()
    env.setdefault("LOCAL_AGENT_BENCH_PI_COMMAND", "npx -y @earendil-works/pi-coding-agent")

    args.results_dir.mkdir(parents=True, exist_ok=True)
    model = _model_for_native(args.model)
    label = args.label or datetime.now().strftime("%Y%m%d")
    output_prefix = f"platform-native-repeat_{_slug(args.benchmark.stem)}_{_slug(args.runtime)}_{_slug(args.model)}_{label}"

    run_paths: list[Path] = []
    failures = 0
    started_all = time.monotonic()

    for run_index in range(1, args.runs + 1):
        output = args.results_dir / f"{output_prefix}_run{run_index}.json"
        run_paths.append(output)
        if output.exists() and not args.force:
            print(f"[{run_index}/{args.runs}] skip existing -> {output.name}", flush=True)
            continue

        cmd = [
            sys.executable,
            "-m",
            "local_agent_bench",
            "run-platform-native",
            "--runtime",
            args.runtime,
            "--model",
            model,
            "--benchmark",
            str(args.benchmark),
            "--output",
            str(output),
            "--runtime-timeout",
            str(args.runtime_timeout),
            "--judge-timeout",
            str(args.judge_timeout),
            "--judge-model",
            args.judge_model,
        ]
        if args.skip_preflight:
            cmd.append("--skip-preflight")

        print(f"[{run_index}/{args.runs}] run {args.runtime} {model} -> {output.name}", flush=True)
        started = time.monotonic()
        completed = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False, text=True)
        elapsed = time.monotonic() - started
        status = "pass" if completed.returncode == 0 else f"exit {completed.returncode}"
        if completed.returncode != 0:
            failures += 1
        print(f"[{run_index}/{args.runs}] done {status} in {elapsed:.1f}s", flush=True)

    summary = _summarize(run_paths)
    summary.update(
        {
            "runtime": args.runtime,
            "model": model,
            "benchmark": str(args.benchmark),
            "runs_requested": args.runs,
            "subprocess_failures": failures,
            "elapsed_seconds": round(time.monotonic() - started_all, 3),
            "run_files": [str(path) for path in run_paths if path.exists()],
        }
    )
    summary_path = args.results_dir / f"{output_prefix}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(_format_summary(summary), flush=True)
    print(f"summary -> {summary_path.name}", flush=True)
    return 0 if failures == 0 else 1


def _summarize(paths: list[Path]) -> dict[str, Any]:
    loaded = []
    for path in paths:
        if not path.exists():
            continue
        try:
            loaded.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError) as exc:
            loaded.append((path, {"load_error": str(exc), "results": []}))

    totals = [sum(float(result.get("score", 0.0)) for result in data.get("results", [])) for _, data in loaded]
    task_ids = []
    for _, data in loaded:
        for result in data.get("results", []):
            task_id = result.get("task_id")
            if isinstance(task_id, str) and task_id not in task_ids:
                task_ids.append(task_id)

    per_task = {}
    for task_id in task_ids:
        scores = []
        reasons: dict[str, int] = {}
        max_output_cutoffs = 0
        for _, data in loaded:
            result = next((item for item in data.get("results", []) if item.get("task_id") == task_id), None)
            if not result:
                continue
            score = float(result.get("score", 0.0))
            scores.append(score)
            reason = str(result.get("failure_reason", "UNKNOWN"))
            reasons[reason] = reasons.get(reason, 0) + 1
            final_answer = str(result.get("final_answer", ""))
            if _has_max_output_cutoff(final_answer):
                max_output_cutoffs += 1
        per_task[task_id] = {
            "runs": len(scores),
            "mean_score": _mean(scores),
            "stdev_score": _stdev(scores),
            "pass_count": sum(1 for score in scores if score >= 0.9),
            "failure_reasons": reasons,
            "max_output_cutoffs": max_output_cutoffs,
        }

    return {
        "runs_completed": len(loaded),
        "total_scores": totals,
        "mean_total": _mean(totals),
        "stdev_total": _stdev(totals),
        "min_total": min(totals) if totals else 0.0,
        "max_total": max(totals) if totals else 0.0,
        "per_task": per_task,
    }


def _format_summary(summary: dict[str, Any]) -> str:
    lines = [
        (
            f"Repeated platform-native summary: {summary['runs_completed']} runs, "
            f"mean={summary['mean_total']:.2f}, stdev={summary['stdev_total']:.2f}, "
            f"range={summary['min_total']:.1f}-{summary['max_total']:.1f}"
        )
    ]
    for task_id, stats in summary["per_task"].items():
        lines.append(
            f"- {task_id}: pass {stats['pass_count']}/{stats['runs']}, "
            f"mean={stats['mean_score']:.2f}, cutoffs={stats['max_output_cutoffs']}, "
            f"reasons={stats['failure_reasons']}"
        )
    return "\n".join(lines)


def _model_for_native(model: str) -> str:
    if model.startswith("ollama/"):
        return model
    return f"ollama/{model}"


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _has_max_output_cutoff(text: str) -> bool:
    lowered = text.casefold()
    return "maximum output token limit" in lowered or "response may be incomplete" in lowered


if __name__ == "__main__":
    raise SystemExit(main())
