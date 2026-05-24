# Initial Design

This document captures the initial project direction: evaluate agentic capabilities of local LLM models served by Ollama, with OpenClaw, Hermes, and possibly other runtimes.

## Goal

Build a reproducible benchmark that can run on a laptop-class machine, including setups with limited VRAM.

The benchmark should track the emergence of agentic capabilities:

- tool calling
- filesystem inspection
- weather/current-data lookup
- web search
- browser navigation
- multi-step planning
- error recovery

The important requirement is diagnosis. If a model cannot list files in a directory or report the current weather, the benchmark must identify whether the likely cause is bad configuration, runtime/tool exposure, invalid tool-call syntax, weak model behavior, or tool execution failure.

## Recommended Project Shape

```text
local-agent-bench/
  benchmarks/
  docs/
  local_agent_bench/
  runners/
  tools/
  tests/
  results/
  reports/
```

Each benchmark task should define:

- task id
- category
- prompt
- expected tools
- expected answer evidence
- success criteria
- optional fixture context

Example:

```json
{
  "id": "fs_list_workspace",
  "category": "filesystem",
  "prompt": "List the files in the current directory.",
  "required_tools": ["list_directory"],
  "allowed_tools": ["list_directory"],
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

## Capability Ladder

| Level | Capability | Example |
| --- | --- | --- |
| 0 | Plain answer only | Answers static prompts |
| 1 | Recognizes missing info | States that a tool is needed |
| 2 | Emits valid tool calls | Calls `list_directory` with valid args |
| 3 | Uses tool result correctly | Names real returned files |
| 4 | Multi-step tool use | Lists files, then reads one |
| 5 | Error recovery | Handles failed path and retries |
| 6 | Web/search grounding | Searches for current information |
| 7 | Browser/navigation | Opens page and follows links |
| 8 | End-to-end agent work | Completes a small repo task |

## Runtime Modes

The benchmark should compare at least three modes.

### Native Tool Calling

The model emits the runtime's expected tool-call format. This tests the real production path, but can be brittle for smaller models.

### Prompted ReAct

The model emits:

```text
Thought: I need to inspect the directory.
Action: list_directory
Action Input: {"path": "."}
```

This is easier for local models and helps separate reasoning from strict function-call formatting.

### Structured JSON Repair

The model emits approximate JSON and the harness validates it. Invalid output is counted but can be repaired or re-prompted in a controlled way.

## First Tasks

Filesystem:

- list files in the current directory
- report the absolute current path
- find a known file
- read a known file and answer from its contents
- recover from a bad path

Weather:

- get current weather for a neutral public city
- answer whether rain is expected in the next 12 hours
- report today's high and low temperature

Web/search:

- search for a latest release/version
- find a repository or documentation page
- open a URL and summarize a page title

Multi-step:

- read user/location context, then fetch weather
- find Markdown files and summarize their purposes
- inspect a GitHub issue and summarize the requested fix

## Scoring

Use partial credit:

| Score | Meaning |
| --- | --- |
| 0.0 | No useful attempt |
| 0.25 | Recognized that a tool/search was needed |
| 0.5 | Called a relevant tool but with wrong args or incomplete use |
| 0.75 | Got correct data but final answer was incomplete |
| 1.0 | Fully correct |

Track:

- model
- quantization
- runtime
- context length
- prompt protocol
- valid tool-call rate
- task success rate
- average steps
- latency
- hardware notes
- failure reason

## Failure Categories

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

## First Milestone

The first milestone is deliberately small:

> Can model X, through runtime Y, list this project directory and report the real files?

If a model cannot do that reliably, weather and browser navigation should wait. More complex tasks would only hide the simpler failure.

## Hardware Notes

For an 8 GB VRAM laptop, compare model classes carefully:

- 3B-ish models: fast baseline, likely weak agentic behavior
- 7B/8B models: practical target class
- 14B quantized models: useful stretch test, probably slower

Always record quantization. Comparing `Q4`, `Q5`, and `Q8` results without labeling them makes the benchmark noisy.
