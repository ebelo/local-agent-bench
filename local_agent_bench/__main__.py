from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from local_agent_bench.backends import RAW_OLLAMA_REACT, build_backend, normalize_runtime
from local_agent_bench.diagnostics import run_diagnostics
from local_agent_bench.metadata import collect_run_metadata
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

    args = parser.parse_args()
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

    results = [run_task(backend, model, task, max_steps=max_steps) for task in tasks]
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


if __name__ == "__main__":
    raise SystemExit(main())
