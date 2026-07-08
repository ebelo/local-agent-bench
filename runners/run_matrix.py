#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS = [
    "granite4.1:3b",
    "ibm/granite4.1:8b",
    "qwen3.5:4b",
    "qwen2.5-coder:7b",
    "qwen3.5:9b",
    "qwen3:8b",
    "gemma4:latest",
    "mistral:7b",
    "mistral-nemo:latest",
    "glm-4.7-flash:latest",
]
DEFAULT_RUNTIMES = [
    "raw-ollama-react",
    "pi-react",
    "openclaw-react",
    "hermes-react",
    "openclaw-native",
    "hermes-native",
    "pi-native",
]
OLLAMA_PREFIX_RUNTIMES = {
    "pi-react",
    "openclaw-react",
    "hermes-react",
    "openclaw-native",
    "hermes-native",
    "pi-native",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the smoke benchmark matrix with resumable outputs.")
    parser.add_argument("--model", action="append", dest="models", help="Model to run. Repeatable.")
    parser.add_argument("--runtime", action="append", dest="runtimes", help="Runtime to run. Repeatable.")
    parser.add_argument("--results-dir", type=Path, default=PROJECT_ROOT / "results")
    parser.add_argument("--benchmark", type=Path, default=PROJECT_ROOT / "benchmarks" / "smoke.json")
    parser.add_argument("--runtime-timeout", type=int, default=300)
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--force", action="store_true", help="Overwrite existing result files.")
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()

    models = args.models or DEFAULT_MODELS
    runtimes = args.runtimes or DEFAULT_RUNTIMES
    args.results_dir.mkdir(parents=True, exist_ok=True)
    existing_results = find_existing_results(args.results_dir)

    env = os.environ.copy()
    env.setdefault("LOCAL_AGENT_BENCH_PI_COMMAND", "npx -y @earendil-works/pi-coding-agent")

    total = len(models) * len(runtimes)
    index = 0
    started_at = time.monotonic()
    failures = 0
    skipped = 0

    for model in models:
        for runtime in runtimes:
            index += 1
            output = args.results_dir / f"{slug(model)}-{slug(runtime)}-smoke.json"
            bench_model = model_for_runtime(model, runtime)
            result_key = (runtime, bench_model)
            fallback_result_key = (runtime, model)
            if not args.force and (output.exists() or result_key in existing_results or fallback_result_key in existing_results):
                skipped += 1
                existing = existing_results.get(result_key) or existing_results.get(fallback_result_key) or output
                print(f"[{index}/{total}] skip existing {runtime} {bench_model} -> {existing.name}", flush=True)
                continue

            cmd = [
                sys.executable,
                "-m",
                "local_agent_bench",
                "run",
                "--runtime",
                runtime,
                "--model",
                bench_model,
                "--benchmark",
                str(args.benchmark),
                "--output",
                str(output),
                "--max-steps",
                str(args.max_steps),
                "--runtime-timeout",
                str(args.runtime_timeout),
            ]
            if args.skip_preflight:
                cmd.append("--skip-preflight")

            print(f"[{index}/{total}] run {runtime} {bench_model} -> {output.name}", flush=True)
            started = time.monotonic()
            completed = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False, text=True)
            elapsed = time.monotonic() - started
            status = "pass" if completed.returncode == 0 else f"exit {completed.returncode}"
            if completed.returncode != 0:
                failures += 1
            print(f"[{index}/{total}] done {status} in {elapsed:.1f}s", flush=True)

    elapsed_total = time.monotonic() - started_at
    print(
        f"matrix complete: {total - skipped} attempted, {skipped} skipped, "
        f"{failures} nonzero exits, {elapsed_total:.1f}s elapsed",
        flush=True,
    )
    return 0 if failures == 0 else 1


def model_for_runtime(model: str, runtime: str) -> str:
    if runtime in OLLAMA_PREFIX_RUNTIMES and not model.startswith("ollama/"):
        return f"ollama/{model}"
    return model


def find_existing_results(results_dir: Path) -> dict[tuple[str, str], Path]:
    results: dict[tuple[str, str], Path] = {}
    for path in results_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        runtime = data.get("runtime")
        model = data.get("model")
        if isinstance(runtime, str) and isinstance(model, str):
            results.setdefault((runtime, model), path)
    return results


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()


if __name__ == "__main__":
    raise SystemExit(main())
