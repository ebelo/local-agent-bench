#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "paper" / "clean-room-matrix.json"
COMPLETED_BENCHMARK_EXIT_CODES = {0, 1}
NATIVE_COMMAND = "run-platform-native"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the paper clean-room benchmark matrix sequentially.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--phase", action="append", help="Phase id to run. Can be repeated. Defaults to included main phases.")
    parser.add_argument("--all-phases", action="store_true", help="Run every phase in the manifest.")
    parser.add_argument("--output-dir", type=Path, help="Override manifest output_dir.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing result files.")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument(
        "--with-latency-gate",
        action="store_true",
        help="Run the manifest latency gate once per phase/runtime/model and skip slow combinations.",
    )
    parser.add_argument(
        "--latency-threshold-seconds",
        type=float,
        help="Override manifest latency_gate.threshold_seconds.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = _load_manifest(args.manifest)
    output_dir = (args.output_dir or PROJECT_ROOT / manifest["output_dir"]).resolve()
    phases = _select_phases(manifest, args.phase, args.all_phases)
    if not phases:
        print("No phases selected.", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.setdefault("OLLAMA_BASE_URL", manifest.get("ollama_base_url", "http://localhost:11434"))
    env.setdefault("LOCAL_AGENT_BENCH_TASK_TIMEOUT", str(manifest.get("default_task_timeout", 0)))
    default_task_timeout = float(manifest.get("default_task_timeout", 0) or 0)
    if default_task_timeout > 0:
        env.setdefault("OLLAMA_TIMEOUT", str(int(math.ceil(default_task_timeout + 5))))

    jobs = list(_expand_jobs(manifest, phases, output_dir))
    print(f"Paper matrix: {len(jobs)} jobs, output={output_dir}", flush=True)
    if args.dry_run:
        if args.with_latency_gate:
            gates = _latency_gate_jobs_for_jobs(manifest, jobs, output_dir, args.latency_threshold_seconds)
            print(f"Latency gates: {len(gates)}")
            for gate in gates:
                print(" ".join(_command_for_job(gate, manifest, args.skip_preflight)))
        for job in jobs:
            print(" ".join(_command_for_job(job, manifest, args.skip_preflight)))
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_manifest_snapshot(manifest, output_dir)
    _maybe_setup_runtime_config(env, args.manifest)

    hard_failures = 0
    completed = 0
    skipped = 0
    latency_skipped = 0
    latency_gate_cache: dict[tuple[str, str, str], dict[str, Any]] = {}
    futility_stats: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    futility_skips: list[dict[str, Any]] = []
    started_all = time.monotonic()

    for index, job in enumerate(jobs, start=1):
        output = job["output"]
        label = f"{job['phase']} {job['runtime']} {job['model']} {job['benchmark_id']} run{job['run_index']}"
        if args.with_latency_gate:
            gate_key = (job["phase"], job["runtime"], job["model"])
            if gate_key not in latency_gate_cache:
                latency_gate_cache[gate_key] = _run_latency_gate(
                    manifest,
                    job,
                    output_dir,
                    env,
                    args.skip_preflight,
                    args.force,
                    args.latency_threshold_seconds,
                )
            gate = latency_gate_cache[gate_key]
            if not gate["passed"]:
                _remove_forced_output(output, args.force)
                latency_skipped += 1
                skipped += 1
                print(
                    f"[{index}/{len(jobs)}] skip slow {label}: {gate['reason']} ({gate.get('latency_s', 0):.1f}s)",
                    flush=True,
                )
                continue

        futility_key = (job["phase"], job["runtime"], job["model"], job["benchmark_id"])
        futility = _futility_verdict(manifest, job, futility_stats.get(futility_key))
        if futility["skip"]:
            _remove_forced_output(output, args.force)
            skipped += 1
            futility_skips.append({**futility, "output": str(output), "run_index": job["run_index"]})
            print(f"[{index}/{len(jobs)}] skip futile {label}: {futility['reason']}", flush=True)
            continue

        if output.exists() and not args.force:
            print(f"[{index}/{len(jobs)}] skip existing {label} -> {output.name}", flush=True)
            skipped += 1
            continue

        cmd = _command_for_job(job, manifest, args.skip_preflight)
        _remove_forced_output(output, args.force)
        print(f"[{index}/{len(jobs)}] run {label}", flush=True)
        started = time.monotonic()
        process = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, text=True, check=False)
        elapsed = time.monotonic() - started

        if output.exists() and process.returncode in COMPLETED_BENCHMARK_EXIT_CODES:
            completed += 1
            _record_futility_result(futility_stats, job, output)
            print(f"[{index}/{len(jobs)}] complete exit={process.returncode} elapsed={elapsed:.1f}s -> {output.name}", flush=True)
            continue

        hard_failures += 1
        print(
            f"[{index}/{len(jobs)}] HARD FAILURE exit={process.returncode} elapsed={elapsed:.1f}s output_exists={output.exists()}",
            file=sys.stderr,
            flush=True,
        )

    elapsed_all = time.monotonic() - started_all
    print(
        (
            f"Paper matrix done: completed={completed}, skipped={skipped}, "
            f"latency_skipped={latency_skipped}, hard_failures={hard_failures}, elapsed={elapsed_all:.1f}s"
        ),
        flush=True,
    )
    if args.with_latency_gate:
        _write_latency_gate_summary(output_dir, latency_gate_cache)
    if futility_skips:
        _write_futility_summary(output_dir, futility_skips)
    return 0 if hard_failures == 0 else 1


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not load manifest {path}: {exc}") from exc


def _write_manifest_snapshot(manifest: dict[str, Any], output_dir: Path) -> None:
    snapshot = output_dir / "manifest.snapshot.json"
    snapshot.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _futility_verdict(manifest: dict[str, Any], job: dict[str, Any], stats: dict[str, Any] | None) -> dict[str, Any]:
    gate = manifest.get("futility_gate", {})
    if not gate.get("enabled", False):
        return {"skip": False}
    if job.get("command") != NATIVE_COMMAND:
        return {"skip": False}
    if stats is None:
        return {"skip": False}
    min_runs = int(gate.get("min_runs", 3))
    max_total_score = float(gate.get("max_total_score", 0.0))
    completed = int(stats.get("completed", 0))
    max_observed = float(stats.get("max_total_score", 0.0))
    if completed >= min_runs and max_observed <= max_total_score:
        return {
            "skip": True,
            "phase": job["phase"],
            "runtime": job["runtime"],
            "model": job["model"],
            "benchmark_id": job["benchmark_id"],
            "completed_runs": completed,
            "max_observed_total_score": max_observed,
            "threshold_total_score": max_total_score,
            "reason": (
                f"{completed} completed runs had max total score {max_observed:.2f} "
                f"<= futility threshold {max_total_score:.2f}"
            ),
        }
    return {"skip": False}


def _record_futility_result(
    futility_stats: dict[tuple[str, str, str, str], dict[str, Any]],
    job: dict[str, Any],
    output: Path,
) -> None:
    key = (job["phase"], job["runtime"], job["model"], job["benchmark_id"])
    stats = futility_stats.setdefault(key, {"completed": 0, "scores": [], "max_total_score": 0.0})
    total = _result_total_score(output)
    if total is None:
        return
    stats["completed"] += 1
    stats["scores"].append(total)
    stats["max_total_score"] = max(float(stats.get("max_total_score", 0.0)), total)


def _result_total_score(output: Path) -> float | None:
    try:
        data = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    results = data.get("results", [])
    if not isinstance(results, list):
        return None
    return float(sum(float(result.get("score", 0.0) or 0.0) for result in results if isinstance(result, dict)))


def _write_futility_summary(output_dir: Path, skips: list[dict[str, Any]]) -> None:
    path = output_dir / "futility-summary.json"
    path.write_text(json.dumps({"skips": skips}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _maybe_setup_runtime_config(env: dict[str, str], manifest_path: Path) -> None:
    flag = env.get("LOCAL_AGENT_BENCH_SETUP_RUNTIME_CONFIGS", "").casefold()
    if flag not in {"1", "true", "yes"}:
        return
    script = PROJECT_ROOT / "scripts" / "setup_runtime_clean_room.py"
    cmd = [sys.executable, str(script), "--manifest", str(manifest_path)]
    print("[runtime-config] configure OpenClaw/Hermes/Pi clean-room providers", flush=True)
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, text=True, check=True)


def _select_phases(manifest: dict[str, Any], selected: list[str] | None, all_phases: bool) -> list[dict[str, Any]]:
    phases = manifest.get("phases", [])
    if all_phases:
        return phases
    if selected:
        wanted = set(selected)
        unknown = wanted.difference(phase.get("id") for phase in phases)
        if unknown:
            raise SystemExit(f"Unknown phase(s): {', '.join(sorted(unknown))}")
        return [phase for phase in phases if phase.get("id") in wanted]
    return [phase for phase in phases if phase.get("included_in_main_findings")]


def _expand_jobs(manifest: dict[str, Any], phases: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    models = {model["id"]: model for model in manifest.get("models", [])}
    benchmarks = {benchmark["id"]: benchmark for benchmark in manifest.get("benchmarks", [])}
    jobs: list[dict[str, Any]] = []

    for phase in phases:
        for runtime in phase.get("runtimes", []):
            for model_id in phase.get("models", []):
                model = models[model_id]
                for benchmark_id in phase.get("benchmarks", []):
                    benchmark = benchmarks[benchmark_id]
                    for run_index in range(1, int(phase.get("runs", 1)) + 1):
                        name = "_".join(
                            [
                                _slug(manifest["dataset"]),
                                _slug(phase["id"]),
                                _slug(runtime),
                                _slug(model["paper_id"]),
                                _slug(benchmark_id),
                                f"run{run_index:02d}",
                            ]
                        )
                        jobs.append(
                            {
                                "phase": phase["id"],
                                "command": phase.get("command", "run"),
                                "runtime": runtime,
                                "model": model_id,
                                "model_paper_id": model["paper_id"],
                                "benchmark_id": benchmark_id,
                                "benchmark": benchmark["path"],
                                "run_index": run_index,
                                "output": output_dir / f"{name}.json",
                                "runtime_timeout": int(phase.get("runtime_timeout", manifest.get("default_runtime_timeout", 600))),
                                "task_timeout": float(phase.get("task_timeout", manifest.get("default_task_timeout", 0))),
                                "max_steps": int(phase.get("max_steps", manifest.get("default_max_steps", 5))),
                                "latency_threshold_seconds": phase.get("latency_threshold_seconds"),
                                "deterministic_platform_score": bool(phase.get("deterministic_score_only", False)),
                                "skip_preflight": bool(phase.get("skip_preflight", False)),
                            }
                        )
    return jobs


def _latency_gate_jobs_for_jobs(
    manifest: dict[str, Any],
    jobs: list[dict[str, Any]],
    output_dir: Path,
    threshold_override: float | None,
) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    gates = []
    repeats = _latency_gate_repeats(manifest)
    for job in jobs:
        key = (job["phase"], job["runtime"], job["model"])
        if key in seen:
            continue
        seen.add(key)
        for attempt_index in range(1, repeats + 1):
            gates.append(_latency_gate_job(manifest, job, output_dir, threshold_override, attempt_index))
    return gates


def _latency_gate_job(
    manifest: dict[str, Any],
    job: dict[str, Any],
    output_dir: Path,
    threshold_override: float | None,
    attempt_index: int = 1,
) -> dict[str, Any]:
    gate = manifest.get("latency_gate", {})
    benchmarks = {benchmark["id"]: benchmark for benchmark in manifest.get("benchmarks", [])}
    is_native_command = job.get("command") == NATIVE_COMMAND
    benchmark_key = "native_benchmark" if is_native_command else "benchmark"
    benchmark_id = str(gate.get(benchmark_key, "platform-native-latency-gate" if is_native_command else "latency-gate"))
    if benchmark_id not in benchmarks:
        raise SystemExit(f"Latency gate benchmark '{benchmark_id}' not found in manifest.")
    phase_threshold = job.get("latency_threshold_seconds")
    threshold = float(
        threshold_override
        if threshold_override is not None
        else phase_threshold
        if phase_threshold is not None
        else gate.get("threshold_seconds", 20)
    )
    runtime_timeout = int(max(float(gate.get("runtime_timeout", 0) or 0), threshold + 15, 30))
    task_timeout = float(max(float(gate.get("task_timeout", threshold) or threshold), threshold))
    name = "_".join(
        [
            _slug(manifest["dataset"]),
            "latency-gate",
            _slug(job["phase"]),
            _slug(job["runtime"]),
            _slug(job["model_paper_id"]),
            _slug(benchmark_id),
            f"run{attempt_index:02d}",
        ]
    )
    return {
        "phase": f"latency-gate:{job['phase']}",
        "command": job.get("command", "run"),
        "runtime": job["runtime"],
        "model": job["model"],
        "model_paper_id": job["model_paper_id"],
        "benchmark_id": benchmark_id,
        "benchmark": benchmarks[benchmark_id]["path"],
        "run_index": 1,
        "output": output_dir / f"{name}.json",
        "runtime_timeout": runtime_timeout,
        "task_timeout": task_timeout,
        "max_steps": int(gate.get("max_steps", 1)),
        "latency_threshold": threshold,
        "min_score": float(gate.get("min_score", 0.9)),
        "prewarm": bool(gate.get("prewarm", False)),
        "warmup_timeout": float(gate.get("warmup_timeout", max(threshold + 30, 60))),
        "gate_attempt": attempt_index,
        "deterministic_platform_score": is_native_command,
        "skip_preflight": bool(job.get("skip_preflight", False)),
    }


def _run_latency_gate(
    manifest: dict[str, Any],
    job: dict[str, Any],
    output_dir: Path,
    env: dict[str, str],
    skip_preflight: bool,
    force: bool,
    threshold_override: float | None,
) -> dict[str, Any]:
    repeats = _latency_gate_repeats(manifest)
    min_passes = _latency_gate_min_passes(manifest, repeats)
    label = f"{job['phase']} {job['runtime']} {job['model']}"
    attempts = [
        _run_latency_gate_attempt(
            manifest,
            job,
            output_dir,
            env,
            skip_preflight,
            force,
            threshold_override,
            attempt_index,
            label,
        )
        for attempt_index in range(1, repeats + 1)
    ]
    return _combined_latency_gate_verdict(attempts, min_passes)


def _run_latency_gate_attempt(
    manifest: dict[str, Any],
    job: dict[str, Any],
    output_dir: Path,
    env: dict[str, str],
    skip_preflight: bool,
    force: bool,
    threshold_override: float | None,
    attempt_index: int,
    label: str,
) -> dict[str, Any]:
    gate_job = _latency_gate_job(manifest, job, output_dir, threshold_override, attempt_index)
    output = gate_job["output"]
    if output.exists() and not force:
        verdict = _latency_gate_verdict(gate_job, output, returncode=0)
        print(f"[latency-gate] reuse {label} attempt={attempt_index}: {verdict['reason']}", flush=True)
        return verdict

    cmd = _command_for_job(gate_job, manifest, skip_preflight)
    _remove_forced_output(output, force)
    gate_env = env.copy()
    gate_timeout = max(float(gate_job["latency_threshold"]) + 5, float(gate_job["task_timeout"]) + 5)
    gate_env["OLLAMA_TIMEOUT"] = str(int(math.ceil(gate_timeout)))
    print(f"[latency-gate] run {label} attempt={attempt_index} threshold={gate_job['latency_threshold']:.1f}s", flush=True)
    warmup: dict[str, Any] | None = None
    if gate_job.get("prewarm"):
        warmup = _warm_ollama_model(gate_env["OLLAMA_BASE_URL"], gate_job["model"], float(gate_job["warmup_timeout"]))
        warm_status = "ok" if warmup["ok"] else "fail"
        print(f"[latency-gate] warmup {warm_status} {label} attempt={attempt_index}: {warmup['detail']}", flush=True)
        if not warmup["ok"]:
            return {
                "phase": gate_job["phase"].split(":", 1)[-1],
                "runtime": gate_job["runtime"],
                "model": gate_job["model"],
                "output": str(output),
                "threshold_s": float(gate_job["latency_threshold"]),
                "min_score": float(gate_job["min_score"]),
                "returncode": None,
                "passed": False,
                "latency_s": 0.0,
                "attempt": attempt_index,
                "warmup": warmup,
                "reason": f"warmup failed: {warmup['detail']}",
            }
    started = time.monotonic()
    process = subprocess.run(cmd, cwd=PROJECT_ROOT, env=gate_env, text=True, check=False)
    elapsed = time.monotonic() - started
    verdict = _latency_gate_verdict(gate_job, output, process.returncode)
    verdict["subprocess_elapsed_s"] = round(elapsed, 3)
    if warmup is not None:
        verdict["warmup"] = warmup
    status = "pass" if verdict["passed"] else "fail"
    print(f"[latency-gate] {status} {label} attempt={attempt_index}: {verdict['reason']}", flush=True)
    return verdict


def _combined_latency_gate_verdict(attempts: list[dict[str, Any]], min_passes: int) -> dict[str, Any]:
    if not attempts:
        return {"passed": False, "reason": "no latency gate attempts were run", "latency_s": 0.0}
    passed = [attempt for attempt in attempts if attempt.get("passed")]
    base = {
        "phase": attempts[0].get("phase"),
        "runtime": attempts[0].get("runtime"),
        "model": attempts[0].get("model"),
        "threshold_s": attempts[0].get("threshold_s"),
        "min_score": attempts[0].get("min_score"),
        "repeats": len(attempts),
        "min_passes": min_passes,
        "passed_attempts": len(passed),
        "attempts": attempts,
    }
    latencies = [float(attempt.get("latency_s", 0.0) or 0.0) for attempt in attempts if attempt.get("latency_s")]
    if latencies:
        base["latency_s"] = statistics.median(latencies)
    else:
        base["latency_s"] = 0.0
    for attempt in attempts:
        if attempt.get("execution_profile"):
            base["execution_profile"] = attempt["execution_profile"]
            break
    if len(passed) >= min_passes:
        return {
            **base,
            "passed": True,
            "reason": f"{len(passed)}/{len(attempts)} gate attempts passed; median latency {base['latency_s']:.1f}s",
        }
    reasons = "; ".join(str(attempt.get("reason", "")) for attempt in attempts[:3])
    return {
        **base,
        "passed": False,
        "reason": f"{len(passed)}/{len(attempts)} gate attempts passed; {reasons}",
    }


def _warm_ollama_model(base_url: str, model: str, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    payload = {
        "model": _ollama_model_tag(model),
        "messages": [{"role": "user", "content": "Reply with READY."}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 4},
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        elapsed = time.monotonic() - started
        return {"ok": False, "elapsed_s": round(elapsed, 3), "detail": f"HTTP {exc.code}: {body[:200]}"}
    except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        elapsed = time.monotonic() - started
        return {"ok": False, "elapsed_s": round(elapsed, 3), "detail": f"{type(exc).__name__}: {exc}"}
    elapsed = time.monotonic() - started
    content = str(data.get("message", {}).get("content", "")).strip()
    return {"ok": True, "elapsed_s": round(elapsed, 3), "detail": f"loaded in {elapsed:.1f}s; response={content[:40]!r}"}


def _latency_gate_verdict(gate_job: dict[str, Any], output: Path, returncode: int) -> dict[str, Any]:
    base = {
        "phase": gate_job["phase"].split(":", 1)[-1],
        "runtime": gate_job["runtime"],
        "model": gate_job["model"],
        "output": str(output),
        "threshold_s": float(gate_job["latency_threshold"]),
        "min_score": float(gate_job["min_score"]),
        "returncode": returncode,
        "passed": False,
        "latency_s": 0.0,
        "attempt": int(gate_job.get("gate_attempt", 1)),
    }
    if not output.exists():
        return {**base, "reason": f"latency gate produced no JSON output (exit {returncode})"}
    try:
        data = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {**base, "reason": f"latency gate JSON could not be read: {exc}"}
    results = data.get("results", [])
    if not results:
        return {**base, "reason": "latency gate JSON contains no results"}
    result = results[0]
    latency_s = float(result.get("latency_ms", 0.0)) / 1000
    score = float(result.get("score", 0.0) or 0.0)
    final_answer = str(result.get("final_answer", "")).strip()
    threshold = float(gate_job["latency_threshold"])
    min_score = float(gate_job["min_score"])
    verdict = {
        **base,
        "latency_s": latency_s,
        "score": score,
        "failure_reason": result.get("failure_reason"),
        "final_answer_preview": final_answer[:120],
    }
    execution_profile = data.get("metadata", {}).get("execution_profile")
    if execution_profile:
        verdict["execution_profile"] = execution_profile
    if not final_answer:
        return {**verdict, "reason": "empty model response"}
    if latency_s > threshold:
        return {**verdict, "reason": f"latency {latency_s:.1f}s exceeds threshold {threshold:.1f}s"}
    if score < min_score:
        return {**verdict, "reason": f"score {score:.2f} below gate minimum {min_score:.2f}"}
    return {**verdict, "passed": True, "reason": f"latency {latency_s:.1f}s <= {threshold:.1f}s and score {score:.2f}"}


def _write_latency_gate_summary(output_dir: Path, cache: dict[tuple[str, str, str], dict[str, Any]]) -> None:
    path = output_dir / "latency-gate-summary.json"
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        for gate in existing.get("gates", []):
            key = (str(gate.get("phase", "")), str(gate.get("runtime", "")), str(gate.get("model", "")))
            merged[key] = gate
    for gate in cache.values():
        key = (str(gate.get("phase", "")), str(gate.get("runtime", "")), str(gate.get("model", "")))
        merged[key] = gate
    summary = {
        "generated_at_unix": time.time(),
        "gates": list(merged.values()),
        "excluded": [value for value in merged.values() if not value.get("passed")],
    }
    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _remove_forced_output(path: Path, force: bool) -> None:
    if force and path.exists():
        path.unlink()


def _latency_gate_repeats(manifest: dict[str, Any]) -> int:
    gate = manifest.get("latency_gate", {})
    return max(1, int(gate.get("repeats", 1)))


def _latency_gate_min_passes(manifest: dict[str, Any], repeats: int) -> int:
    gate = manifest.get("latency_gate", {})
    return min(repeats, max(1, int(gate.get("min_passes", repeats))))


def _command_for_job(job: dict[str, Any], manifest: dict[str, Any], skip_preflight: bool) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "local_agent_bench",
        job["command"],
        "--runtime",
        job["runtime"],
        "--model",
        _model_for_command(job["model"], job["command"], job["runtime"]),
        "--benchmark",
        job["benchmark"],
        "--output",
        str(job["output"]),
        "--runtime-timeout",
        str(job["runtime_timeout"]),
    ]
    if job["command"] == NATIVE_COMMAND:
        cmd.extend(
            [
                "--judge-model",
                str(manifest.get("judge_model", "ollama/glm-5.2:cloud")),
                "--judge-timeout",
                str(manifest.get("judge_timeout", 120)),
            ]
        )
        if job.get("deterministic_platform_score"):
            cmd.append("--deterministic-score-only")
    else:
        cmd.extend(["--max-steps", str(job["max_steps"])])
        if job["task_timeout"] > 0:
            cmd.extend(["--task-timeout", str(job["task_timeout"])])
    if skip_preflight or job.get("skip_preflight"):
        cmd.append("--skip-preflight")
    return cmd


def _model_for_command(model: str, command: str, runtime: str) -> str:
    if runtime != "raw-ollama-react" and not model.startswith("ollama/"):
        return f"ollama/{model}"
    return model


def _ollama_model_tag(model: str) -> str:
    return model.removeprefix("ollama/")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()


if __name__ == "__main__":
    raise SystemExit(main())
