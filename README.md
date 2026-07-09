# Local Agent Bench

Local Agent Bench is a small benchmark harness for evaluating agentic capabilities of local LLMs served by Ollama and agent runtimes such as OpenClaw, Hermes, and other future adapters.

The first goal is practical: when a local model cannot list files or fetch current weather, the benchmark should say whether the failure came from the model, the prompt/tool-call protocol, the runtime adapter, or the local configuration.

## Scope

The benchmark tracks a capability ladder:

| Level | Capability | Example |
| --- | --- | --- |
| 0 | Plain answer | Answer a static factual prompt |
| 1 | Recognizes missing context | Says a directory or weather tool is needed |
| 2 | Emits a valid tool call | Calls `list_directory` with valid JSON args |
| 3 | Uses tool output correctly | Names actual files returned by the tool |
| 4 | Multi-step tool use | Reads a file found by listing a directory |
| 5 | Error recovery | Retries after a bad path or failed request |
| 6 | Web/search grounding | Searches live information and cites the result |
| 7 | Browser navigation | Opens pages, follows links, extracts an answer |
| 8 | End-to-end agent work | Completes a small task with planning and tools |

## Why This Exists

Local agent failures are often misdiagnosed. "The model cannot use tools" can mean several different things:

- Ollama is not reachable.
- The requested model is not installed.
- The runtime did not expose tools to the model.
- The model emitted malformed JSON.
- The model chose the wrong tool.
- The tool worked, but the model ignored the result.
- Network access failed for the tool itself.
- The final answer hallucinated instead of using observed data.

This project records those failure layers explicitly.

## Quick Start

Requirements:

- Python 3.11+
- Ollama running locally
- At least one Ollama model installed

From this directory:

```bash
python3 -m local_agent_bench diagnose
python3 -m local_agent_bench run --model llama3.1:8b
```

You can also set the model through an environment variable:

```bash
export OLLAMA_MODEL=qwen2.5-coder:7b
python3 -m local_agent_bench run
```

The default Ollama endpoint is `http://localhost:11434`. Override it with:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
```

Select a runtime adapter with `--runtime`:

```bash
python3 -m local_agent_bench run --runtime raw-ollama-react --model qwen2.5-coder:7b
python3 -m local_agent_bench run --runtime openclaw-react --model ollama/qwen2.5-coder:7b
python3 -m local_agent_bench run --runtime hermes-react --model <provider/model>
python3 -m local_agent_bench run --runtime pi-react --model ollama/qwen2.5-coder:7b
python3 -m local_agent_bench run --runtime openclaw-native --model ollama/qwen2.5-coder:7b
python3 -m local_agent_bench run --runtime hermes-native --model ollama/qwen2.5-coder:7b
python3 -m local_agent_bench run --runtime pi-native --model ollama/qwen2.5-coder:7b
```

`openclaw-react` calls `openclaw infer model run --local --json`; `hermes-react` calls `hermes chat --query --quiet --ignore-rules`; `pi-react` calls `pi --print --no-session --no-tools --no-context-files`.
These adapters use the same benchmark ReAct protocol and the same harness-owned tools as the raw Ollama runner, so task evidence and scoring stay comparable across runtimes.
The OpenClaw adapter uses the stateless infer path instead of a chat-agent turn, avoiding runtime tools, session transcript, and workspace instruction injection in public benchmark output.
The Hermes adapter runs with `--ignore-rules` and defaults to the `safe` toolset to avoid user memory, project instructions, file tools, and terminal tools.
Hermes may reject small local models if their configured context window is below its agent minimum; treat that as a runtime-configuration failure, not a benchmark-task failure.
Pi needs a configured local model provider in `~/.pi/agent/models.json` or a custom `PI_CODING_AGENT_DIR`. If `pi` is not installed on `PATH`, set `LOCAL_AGENT_BENCH_PI_COMMAND`, for example `LOCAL_AGENT_BENCH_PI_COMMAND="npx -y @earendil-works/pi-coding-agent"`.

`openclaw-native`, `hermes-native`, and `pi-native` run a platform-native agent turn and add `native_platform_tool_score` to each result. This score checks whether the platform/model emitted native tool-call traces for the task's required tools and whether required arguments were present. It is intentionally separate from the ReAct score: a model can pass `raw-ollama-react` while failing native tool-call formation inside a platform.

Platform-native use-case suites can be run with an LLM judge:

```bash
python3 -m local_agent_bench run-platform-native \
  --runtime pi-native \
  --model ollama/ornith:9b \
  --benchmark benchmarks/platform_native.json
```

`benchmarks/platform_native.json` checks practical native use cases at the level of filesystem, weather, and recovery tasks. `benchmarks/platform_native_ladder.json` probes harder capability-ladder levels 6-8: live web/API grounding, local HTML/Markdown link navigation, and end-to-end project-health/release-brief tasks.

## Initial Benchmark

The first benchmark file is [benchmarks/smoke.json](benchmarks/smoke.json). It checks:

- current working directory inspection
- directory listing
- reading a known fixture file
- live weather lookup for Berlin, Germany
- a simple multi-step "read then answer" task

The weather tool uses Open-Meteo and does not need an API key.

The next benchmark tier is [benchmarks/agentic.json](benchmarks/agentic.json). It checks:

- recovery after an intentional bad file path
- grounding an answer in fixture content instead of prior knowledge
- synthesizing facts from two files
- choosing only the relevant tool when other tools are available
- conditional branching from a file observation into a weather lookup

Run it with:

```bash
python3 -m local_agent_bench run --runtime pi-react --model ollama/qwen3.5:9b --benchmark benchmarks/agentic.json
```

The platform-native ladder suite is [benchmarks/platform_native_ladder.json](benchmarks/platform_native_ladder.json). It is designed for native runtimes and asks harder use-case tasks:

- level 6: live web/API grounding with cited evidence
- level 7: local HTML and Markdown link navigation
- level 8: multi-source synthesis, live data, and command execution

Run it with:

```bash
python3 -m local_agent_bench run-platform-native --runtime pi-native --model ollama/ornith:9b --benchmark benchmarks/platform_native_ladder.json
```

`run` performs a preflight check before executing benchmark tasks. Use `--skip-preflight` only when intentionally testing degraded configuration behavior.

`--task-timeout` sets a per-task timeout in seconds. Tasks that exceed this threshold are auto-failed with `TIMEOUT` as the failure reason. This is useful for discriminating between models that can complete tasks correctly but too slowly to be usable in interactive agent workflows. A threshold of 30 seconds per task is recommended as a practical usability cutoff. Set to 0 (default) to disable the timeout.

## Task Schema

New tasks should use explicit tool and assertion fields:

```json
{
  "id": "fs_list_project",
  "category": "filesystem",
  "prompt": "List the files and folders in the current project directory.",
  "required_tools": ["list_directory"],
  "allowed_tools": ["list_directory"],
  "requires_network": false,
  "diagnostic_layer": "tool_protocol",
  "assertions": [
    {
      "type": "tool_result_contains",
      "tool": "list_directory",
      "path": "entries[].name",
      "value": "README.md"
    },
    {
      "type": "answer_contains_all",
      "values": ["README.md", "benchmarks", "local_agent_bench"]
    }
  ]
}
```

See [docs/task-schema.md](docs/task-schema.md) for the supported assertion types.

## Runtimes

Current:

- `raw-ollama-react`: a minimal ReAct loop using Ollama's local HTTP API.
- `openclaw-react`: the same ReAct loop, with assistant turns produced through `openclaw infer model run --local --json`.
- `hermes-react`: the same ReAct loop, with assistant turns produced through `hermes chat --query --quiet --ignore-rules`.
- `pi-react`: the same ReAct loop, with assistant turns produced through Pi's print mode and no Pi tools/session/context files.
- `openclaw-native`: an OpenClaw agent turn where OpenClaw owns native tool-call formation.
- `hermes-native`: a Hermes agent turn where Hermes owns native tool-call formation.

Planned:

- deeper native runtime trace import for full tool execution evidence
- `baseline`: run with a known strong hosted model to establish a ceiling

## Scoring

Each task receives:

- `score`: `0.0`, `0.25`, `0.5`, `0.75`, or `1.0`
- `failure_reason`: one of the diagnostic categories below
- `tool_calls`: tools requested by the model
- `tool_results`: whether local tools succeeded or failed
- `final_answer`: the model's final response
- `native_platform_tool_score`: present for native platform runtimes, with detected native calls, missing required tools, and missing required arguments

Failure reasons:

- `PASS`
- `OLLAMA_UNREACHABLE`
- `MODEL_NOT_INSTALLED`
- `NO_TOOL_ATTEMPT`
- `INVALID_TOOL_SYNTAX`
- `WRONG_TOOL`
- `BAD_ARGUMENTS`
- `TOOL_EXECUTION_FAILED`
- `IGNORED_TOOL_RESULT`
- `HALLUCINATED_RESULT`
- `MISSING_REQUIRED_TOOL`
- `NO_NATIVE_TOOL_ATTEMPT`
- `NATIVE_MISSING_REQUIRED_TOOL`
- `NATIVE_MISSING_REQUIRED_ARGUMENT`
- `NATIVE_WRONG_TOOL`
- `FORBIDDEN_TOOL`
- `ASSERTION_FAILED`
- `CONTEXT_LOSS`
- `TIMEOUT`
- `RUNTIME_UNAVAILABLE`
- `RUNTIME_ERROR`
- `UNKNOWN_FAILURE`

Results also include assertion-level details so a partial failure can show exactly which condition failed.

## Diagnostics

`diagnose` reports checks by layer:

- `host`: Python and platform metadata
- `configuration`: Ollama CLI/API reachability and model availability
- `configuration`: OpenClaw/Hermes CLI availability for CLI-backed runtimes
- `tooling`: local filesystem tools, known-location fallback, and composed weather tool
- `network`: external API access needed by live-data tasks

This separation is intentional. A weather failure caused by Open-Meteo reachability should not be counted as a model failure.

## Public Reproducibility

The benchmark is designed to be reproducible on different hardware. Results should always include:

- machine model
- GPU/VRAM
- OS
- Ollama version
- model name and quantization
- runtime adapter
- prompt protocol
- benchmark commit SHA

Generated result JSON redacts the local project root and home directory as `<PROJECT_ROOT>` and `<HOME>`. Do not commit raw, unredacted benchmark results from local machines.

CLI adapter binaries can be overridden with `LOCAL_AGENT_BENCH_OPENCLAW_BIN` and `LOCAL_AGENT_BENCH_HERMES_BIN`. Pi's command can be overridden with `LOCAL_AGENT_BENCH_PI_COMMAND`. OpenClaw thinking can be set with `LOCAL_AGENT_BENCH_OPENCLAW_THINKING`; Hermes ReAct toolsets can be set with `LOCAL_AGENT_BENCH_HERMES_TOOLSETS`, and Hermes native toolsets with `LOCAL_AGENT_BENCH_HERMES_NATIVE_TOOLSETS`.

## Design Notes

The project intentionally starts with a ReAct-style protocol instead of relying only on native tool calling. Many small local models can reason about tool use but struggle with strict tool-call envelopes. ReAct gives a useful baseline; native function calling can then be added as a separate mode and compared fairly.

See [docs/initial-design.md](docs/initial-design.md) for the fuller plan captured from the initial chat.
