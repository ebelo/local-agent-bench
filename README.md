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

## Initial Benchmark

The first benchmark file is [benchmarks/smoke.json](benchmarks/smoke.json). It checks:

- current working directory inspection
- directory listing
- reading a known fixture file
- live weather lookup for Berlin, Germany
- a simple multi-step "read then answer" task

The weather tool uses Open-Meteo and does not need an API key.

`run` performs a preflight check before executing benchmark tasks. Use `--skip-preflight` only when intentionally testing degraded configuration behavior.

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

- `raw-ollama`: a minimal ReAct loop using Ollama's local HTTP API

Planned:

- `openclaw`: run the same tasks through OpenClaw's agent runtime
- `hermes`: run the same tasks through Hermes
- `baseline`: run with a known strong hosted model to establish a ceiling

## Scoring

Each task receives:

- `score`: `0.0`, `0.25`, `0.5`, `0.75`, or `1.0`
- `failure_reason`: one of the diagnostic categories below
- `tool_calls`: tools requested by the model
- `tool_results`: whether local tools succeeded or failed
- `final_answer`: the model's final response

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
- `FORBIDDEN_TOOL`
- `ASSERTION_FAILED`
- `CONTEXT_LOSS`
- `TIMEOUT`
- `UNKNOWN_FAILURE`

Results also include assertion-level details so a partial failure can show exactly which condition failed.

## Diagnostics

`diagnose` reports checks by layer:

- `host`: Python and platform metadata
- `configuration`: Ollama CLI/API reachability and model availability
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

## Design Notes

The project intentionally starts with a ReAct-style protocol instead of relying only on native tool calling. Many small local models can reason about tool use but struggle with strict tool-call envelopes. ReAct gives a useful baseline; native function calling can then be added as a separate mode and compared fairly.

See [docs/initial-design.md](docs/initial-design.md) for the fuller plan captured from the initial chat.
