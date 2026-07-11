#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "paper" / "clean-room-matrix.json"
DEFAULT_CONTEXT_WINDOW = 131072
DEFAULT_OPENCLAW_MAX_TOKENS = 384


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure OpenClaw, Hermes, and Pi for the Docker clean-room runtime profile.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--ollama-base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434"))
    parser.add_argument("--ollama-openai-base-url", default=os.environ.get("LOCAL_AGENT_BENCH_OLLAMA_OPENAI_BASE_URL"))
    parser.add_argument(
        "--ollama-api-key",
        default=os.environ.get("LOCAL_AGENT_BENCH_OLLAMA_API_KEY", os.environ.get("OLLAMA_API_KEY", "ollama-local")),
    )
    parser.add_argument(
        "--context-window",
        type=int,
        default=int(os.environ.get("LOCAL_AGENT_BENCH_MODEL_CONTEXT_WINDOW", str(DEFAULT_CONTEXT_WINDOW))),
    )
    parser.add_argument(
        "--openclaw-max-tokens",
        type=int,
        default=int(os.environ.get("LOCAL_AGENT_BENCH_OPENCLAW_MAX_TOKENS", str(DEFAULT_OPENCLAW_MAX_TOKENS))),
    )
    parser.add_argument("--openclaw-bin", default=os.environ.get("LOCAL_AGENT_BENCH_OPENCLAW_BIN", "openclaw"))
    parser.add_argument("--hermes-bin", default=os.environ.get("LOCAL_AGENT_BENCH_HERMES_BIN", "hermes"))
    parser.add_argument("--hermes-provider", default=os.environ.get("LOCAL_AGENT_BENCH_HERMES_PROVIDER", "custom"))
    parser.add_argument("--skip-openclaw", action="store_true")
    parser.add_argument("--skip-hermes", action="store_true")
    parser.add_argument("--skip-pi", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = _load_manifest(args.manifest)
    model_ids = _model_ids(manifest)
    openclaw_model_ids = _openclaw_model_ids(manifest, model_ids)
    ollama_base_url = args.ollama_base_url.rstrip("/")
    ollama_openai_base_url = (args.ollama_openai_base_url or f"{ollama_base_url}/v1").rstrip("/")

    if not args.skip_openclaw:
        patch = build_openclaw_patch(
            openclaw_model_ids,
            ollama_base_url,
            args.context_window,
            args.openclaw_max_tokens,
            args.ollama_api_key,
        )
        if args.dry_run:
            print(json.dumps({"openclaw_patch": patch}, indent=2))
        else:
            _configure_openclaw(args.openclaw_bin, patch)

    if not args.skip_hermes:
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "hermes": {
                            "provider": args.hermes_provider,
                            "base_url": ollama_openai_base_url,
                            "default": model_ids[0],
                            "context_length": args.context_window,
                        }
                    },
                    indent=2,
                )
            )
        else:
            _configure_hermes(args.hermes_bin, args.hermes_provider, ollama_openai_base_url, model_ids[0], args.context_window)

    if not args.skip_pi:
        config = build_pi_models_config(model_ids, ollama_openai_base_url)
        if args.dry_run:
            print(json.dumps({"pi_models": config}, indent=2))
        else:
            path = _write_pi_models_config(config)
            print(f"Configured Pi models: {path}", file=sys.stderr)

    return 0


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not load manifest {path}: {exc}") from exc


def _model_ids(manifest: dict[str, Any]) -> list[str]:
    models = [str(model["id"]) for model in manifest.get("models", []) if "id" in model]
    if not models:
        raise SystemExit("Manifest has no models.")
    return models


def _openclaw_model_ids(manifest: dict[str, Any], model_ids: list[str]) -> list[str]:
    ids = list(model_ids)
    judge_model = str(manifest.get("judge_model", "")).strip()
    if judge_model.startswith("ollama/"):
        judge_model = judge_model.split("/", 1)[1]
    if judge_model and judge_model not in ids:
        ids.append(judge_model)
    return ids


def build_openclaw_patch(
    model_ids: list[str],
    ollama_base_url: str,
    context_window: int = DEFAULT_CONTEXT_WINDOW,
    max_tokens: int = DEFAULT_OPENCLAW_MAX_TOKENS,
    api_key: str = "ollama-local",
) -> dict[str, Any]:
    model_rows = [
        {
            "id": model_id,
            "name": model_id,
            "contextWindow": context_window,
            "contextTokens": context_window,
            "maxTokens": max_tokens,
            "compat": {
                "supportsDeveloperRole": False,
                "supportsReasoningEffort": False,
            },
        }
        for model_id in model_ids
    ]
    return {
        "models": {
            "mode": "merge",
            "providers": {
                "ollama": {
                    "baseUrl": ollama_base_url.rstrip("/"),
                    "api": "ollama",
                    "apiKey": api_key,
                    "timeoutSeconds": 180,
                    "models": model_rows,
                }
            },
        }
    }


def build_pi_models_config(model_ids: list[str], ollama_openai_base_url: str) -> dict[str, Any]:
    return {
        "providers": {
            "ollama": {
                "baseUrl": ollama_openai_base_url.rstrip("/"),
                "api": "openai-completions",
                "apiKey": "ollama-local",
                "compat": {
                    "supportsDeveloperRole": False,
                    "supportsReasoningEffort": False,
                },
                "models": [{"id": model_id} for model_id in model_ids],
            }
        }
    }


def _configure_openclaw(binary: str, patch: dict[str, Any]) -> None:
    _require_binary(binary)
    subprocess.run(
        [binary, "config", "patch", "--stdin"],
        input=json.dumps(patch),
        text=True,
        check=True,
    )
    subprocess.run([binary, "config", "validate"], text=True, check=True)


def _configure_hermes(binary: str, provider: str, base_url: str, default_model: str, context_length: int) -> None:
    _require_binary(binary)
    settings = {
        "model.provider": provider,
        "model.base_url": base_url,
        "model.default": default_model,
        "model.context_length": str(context_length),
    }
    for key, value in settings.items():
        subprocess.run([binary, "config", "set", key, value], text=True, check=True)


def _write_pi_models_config(config: dict[str, Any]) -> Path:
    path = Path.home() / ".pi" / "agent" / "models.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _require_binary(binary: str) -> None:
    if shutil.which(binary) is None:
        raise SystemExit(f"Required runtime binary not found on PATH: {binary}")


if __name__ == "__main__":
    raise SystemExit(main())
