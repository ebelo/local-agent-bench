#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "paper" / "clean-room-matrix.json"
T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate clean-room paper results into JSON and Markdown tables.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    results_dir = (args.results_dir or PROJECT_ROOT / manifest["output_dir"]).resolve()
    output_json = args.output_json or results_dir / "summary.json"
    output_md = args.output_md or PROJECT_ROOT / "paper" / "clean-room-results.md"

    summary = aggregate(manifest, results_dir)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(summary) + "\n", encoding="utf-8")
    print(f"summary json -> {output_json}")
    print(f"summary md   -> {output_md}")
    return 0


def aggregate(manifest: dict[str, Any], results_dir: Path) -> dict[str, Any]:
    files = sorted(results_dir.glob("*.json"))
    latency_gate_summary = _load_latency_gate_summary(results_dir)
    rows = []
    load_errors = []
    latency_gate_result_file_count = 0
    benchmark_result_file_count = 0
    for path in files:
        if path.name in {"manifest.snapshot.json", "latency-gate-summary.json", "summary.json"}:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            load_errors.append({"path": str(path), "error": str(exc)})
            continue
        if not isinstance(data.get("results"), list):
            continue
        if _is_latency_gate_result(path, data):
            latency_gate_result_file_count += 1
            continue
        benchmark_result_file_count += 1
        rows.append(_row_from_result(path, data))

    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["phase"], row["runtime"], row["model"], row["benchmark_id"])
        groups[key].append(row)

    aggregates = [_aggregate_group(key, group_rows) for key, group_rows in sorted(groups.items())]
    execution_profiles = _execution_profiles(rows, latency_gate_summary)
    return {
        "dataset": manifest["dataset"],
        "results_dir": str(results_dir),
        "execution_profiles": execution_profiles,
        "json_file_count": len(files),
        "result_file_count": benchmark_result_file_count,
        "latency_gate_result_file_count": latency_gate_result_file_count,
        "loaded_run_count": len(rows),
        "load_errors": load_errors,
        "latency_gate_summary": latency_gate_summary,
        "aggregates": aggregates,
        "runs": rows,
    }


def _execution_profiles(rows: list[dict[str, Any]], latency_gate_summary: dict[str, Any] | None) -> list[str]:
    profiles = {str(row["execution_profile"]) for row in rows if row.get("execution_profile")}
    if latency_gate_summary:
        for gate in latency_gate_summary.get("gates", []):
            if gate.get("execution_profile"):
                profiles.add(str(gate["execution_profile"]))
    return sorted(profiles)


def _is_latency_gate_result(path: Path, data: dict[str, Any]) -> bool:
    metadata = data.get("metadata", {})
    benchmark_path = str(data.get("benchmark") or metadata.get("benchmark") or "")
    parts = path.stem.split("_")
    return (len(parts) > 1 and parts[1] == "latency-gate") or Path(benchmark_path).stem == "latency_gate"


def _load_latency_gate_summary(results_dir: Path) -> dict[str, Any] | None:
    path = results_dir / "latency-gate-summary.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"load_error": str(exc), "path": str(path)}


def _row_from_result(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("metadata", {})
    benchmark_path = str(data.get("benchmark") or metadata.get("benchmark") or "")
    scores = [float(result.get("score", 0.0)) for result in data.get("results", [])]
    latencies = [float(result.get("latency_ms", 0.0)) for result in data.get("results", [])]
    failures: dict[str, int] = {}
    for result in data.get("results", []):
        reason = str(result.get("failure_reason", "UNKNOWN"))
        failures[reason] = failures.get(reason, 0) + 1

    parts = path.stem.split("_")
    phase = parts[1] if len(parts) >= 6 else "unknown"
    benchmark_id = parts[-2] if len(parts) >= 6 else Path(benchmark_path).stem
    return {
        "file": str(path),
        "phase": phase,
        "runtime": str(data.get("runtime") or metadata.get("runtime") or "unknown"),
        "model": str(data.get("model") or metadata.get("model") or "unknown"),
        "execution_profile": metadata.get("execution_profile"),
        "benchmark": benchmark_path,
        "benchmark_id": benchmark_id,
        "score_total": sum(scores),
        "task_count": len(scores),
        "score_fraction": (sum(scores) / len(scores)) if scores else 0.0,
        "latency_ms_total": sum(latencies),
        "latency_ms_mean": (sum(latencies) / len(latencies)) if latencies else 0.0,
        "failure_reasons": failures,
        "git_commit": metadata.get("git_commit"),
        "python": metadata.get("python"),
        "platform": metadata.get("platform"),
    }


def _aggregate_group(key: tuple[str, str, str, str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    phase, runtime, model, benchmark_id = key
    totals = [row["score_total"] for row in rows]
    fractions = [row["score_fraction"] for row in rows]
    latencies = [row["latency_ms_mean"] / 1000 for row in rows]
    failure_reasons: dict[str, int] = {}
    for row in rows:
        for reason, count in row["failure_reasons"].items():
            failure_reasons[reason] = failure_reasons.get(reason, 0) + count

    return {
        "phase": phase,
        "runtime": runtime,
        "model": model,
        "benchmark_id": benchmark_id,
        "runs": len(rows),
        "task_count": rows[0]["task_count"] if rows else 0,
        "mean_total": _mean(totals),
        "stdev_total": _stdev(totals),
        "ci95_total": _ci95(totals),
        "mean_fraction": _mean(fractions),
        "mean_latency_s_per_task": _mean(latencies),
        "failure_reasons": failure_reasons,
        "files": [row["file"] for row in rows],
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Clean-Room Result Summary",
        "",
        f"Dataset: `{summary['dataset']}`",
        f"Result directory: `{summary['results_dir']}`",
    ]
    if summary.get("execution_profiles"):
        lines.append(f"Execution profile(s): `{', '.join(summary['execution_profiles'])}`")
    lines.append(f"Loaded benchmark runs: `{summary['loaded_run_count']}` from `{summary['result_file_count']}` benchmark JSON files")
    if summary.get("latency_gate_result_file_count"):
        lines.append(f"Latency gate result files: `{summary['latency_gate_result_file_count']}`")
    lines.append("")
    if summary["load_errors"]:
        lines.extend(["## Load Errors", ""])
        for error in summary["load_errors"]:
            lines.append(f"- `{error['path']}`: {error['error']}")
        lines.append("")

    gate_summary = summary.get("latency_gate_summary")
    if gate_summary:
        lines.extend(["## Latency Gate", ""])
        if gate_summary.get("load_error"):
            lines.append(f"- Could not load latency gate summary: {gate_summary['load_error']}")
        else:
            gates = gate_summary.get("gates", [])
            excluded = gate_summary.get("excluded", [])
            lines.append(f"Evaluated gates: `{len(gates)}`; excluded combinations: `{len(excluded)}`")
            if excluded:
                lines.append("")
                lines.append("| Phase | Runtime | Model | Latency | Reason |")
                lines.append("|---|---|---|---:|---|")
                for item in excluded:
                    lines.append(
                        "| {phase} | {runtime} | {model} | {latency:.1f}s | {reason} |".format(
                            phase=item.get("phase", ""),
                            runtime=item.get("runtime", ""),
                            model=item.get("model", ""),
                            latency=float(item.get("latency_s", 0.0) or 0.0),
                            reason=str(item.get("reason", "")),
                        )
                    )
        lines.append("")

    by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in summary["aggregates"]:
        by_phase[row["phase"]].append(row)

    for phase, rows in sorted(by_phase.items()):
        lines.extend([f"## {phase}", ""])
        lines.append("| Runtime | Model | Benchmark | Runs | Mean Score | 95% CI | Avg s/task | Main Failures |")
        lines.append("|---|---|---|---:|---:|---:|---:|---|")
        for row in rows:
            failures = _format_failures(row["failure_reasons"])
            lines.append(
                "| {runtime} | {model} | {benchmark} | {runs} | {score:.2f}/{tasks} | ±{ci:.2f} | {latency:.1f} | {failures} |".format(
                    runtime=row["runtime"],
                    model=row["model"],
                    benchmark=row["benchmark_id"],
                    runs=row["runs"],
                    score=row["mean_total"],
                    tasks=row["task_count"],
                    ci=row["ci95_total"],
                    latency=row["mean_latency_s_per_task"],
                    failures=failures,
                )
            )
        lines.append("")
    if not by_phase:
        lines.extend(["No benchmark runs passed the latency gate.", ""])
    return "\n".join(lines)


def _format_failures(failures: dict[str, int]) -> str:
    if not failures:
        return ""
    ordered = sorted(failures.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{reason}={count}" for reason, count in ordered[:3])


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def _ci95(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    stdev = _stdev(values)
    critical = T_CRITICAL_95.get(len(values) - 1, 1.96)
    return critical * stdev / math.sqrt(len(values))


if __name__ == "__main__":
    raise SystemExit(main())
