# Local Agent Bench: A Diagnostic Benchmark for Local LLM Tool Use

*Why "the model can't use tools" is almost never the whole story, and how a small open-source harness separates model failures from runtime failures from network failures — with statistical rigor.*

---

## The Problem With Local Agent Benchmarks

When a local LLM fails to list a directory or fetch the weather, the typical response is: "the model can't use tools." That diagnosis is almost always wrong — or at least incomplete. Between the model's token output and a successful tool call, there are half a dozen things that can break:

- The model emitted valid reasoning but malformed JSON arguments.
- The model called the right tool with the wrong arguments.
- The runtime adapter didn't pass the tool definitions to the model.
- The tool executed successfully, but the model ignored the result and hallucinated.
- The network was down, so the tool itself failed.
- The runtime captured the wrong output stream and never saw the model's response.
- The model returned an empty string after a tool observation — a context-loss issue, not a tool-protocol issue.

Most benchmark harnesses conflate these layers. They give you a single score and let you guess the rest. Local Agent Bench was built to stop guessing.

## What Local Agent Bench Does

Local Agent Bench is a small, open-source Python harness that evaluates the agentic capabilities of local LLMs served through Ollama and agent runtimes such as OpenClaw, Hermes, and Pi. It now separates evaluation into two sequential topics:

1. **Controlled tool protocol** — the harness owns the tools, prompt, parser, and assertions. This is the fair cross-model comparison layer.
2. **Platform-native use cases** — the runtime owns the tools, context, and agent loop. The benchmark asks useful tasks and judges whether the agent actually completed them.

Both topics use a 0.0 to 1.0 task score and explicit failure reasons, but they answer different questions. The controlled suite asks whether the model can follow the benchmark's tool protocol. The platform-native suite asks whether a model/runtime combination is useful in its natural environment.

The controlled suite uses a ReAct-style protocol: the model is given a system prompt describing available tools, and it must respond with either a tool call (Action + Action Input with JSON arguments) or a Final Answer. The harness owns the tools — `get_cwd`, `list_directory`, `read_file`, `get_weather` — so tool execution is deterministic and identical across all runtimes. The only variable is the model's reasoning and format compliance.

The platform-native suite uses use-case prompts instead: "list the project", "read this fixture", "recover from a missing path", "get current weather". It lets Pi, Hermes, or OpenClaw choose their own native tools. Scoring combines deterministic answer checks with an LLM judge that evaluates task completion and evidence of real tool use.

There is also a harder platform-native ladder suite, `benchmarks/platform_native_ladder.json`, for probing levels 6-8: live web/API grounding, local HTML/Markdown link navigation, and end-to-end project-health or release-readiness work.

Because native platform runs are probabilistic, especially through Pi, the ladder suite should be interpreted through independent repeated runs rather than a single transcript. The repeat runner stores one result file per run and summarizes mean score, variance, task pass counts, and output-limit cutoffs.

### What Is ReAct?

ReAct (short for **Re**asoning + **Act**ing) is a prompting framework introduced by Yao et al. in 2022. The core idea is simple but powerful: instead of asking an LLM to just *think* or just *act*, you ask it to alternate between the two in a tight loop.

A pure reasoning model thinks through a problem step by step but can't interact with the outside world — it can't check a file, look up the weather, or query a database. A pure acting model fires off tool calls but has no visible reasoning about *why* it's calling them or *what* to do with the result. ReAct combines both: the model explicitly reasons about what it needs to do, takes an action (a tool call), observes what happened, and then reasons again about the next step.

The protocol defines three roles for the model's output:

- **Thought** — The model's reasoning about what to do next. This is where the model says "I need to list the directory to see what files are available" or "The file doesn't exist, so I should try listing the directory to find the correct path."
- **Action** — The name of the tool to call (e.g., `list_directory`).
- **Action Input** — The arguments for that tool, formatted as JSON (e.g., `{"path": "."}`).

The harness then executes the tool and returns the result as an **Observation** — a JSON blob with whatever the tool produced. The model sees the observation and starts the cycle again: new Thought → new Action → new Action Input, until it has enough information to produce a **Final Answer** instead of another tool call.

Here's what a concrete ReAct exchange looks like for the "List project" smoke task:

```text
[System prompt lists available tools: get_cwd, list_directory, read_file, get_weather]

User: List the contents of the current project directory.

Assistant:
Thought: I need to see what files are in the current directory. I'll call
the list_directory tool with path "."
Action: list_directory
Action Input: {"path": "."}

[Harness executes list_directory and returns:]
Observation: {"entries": ["README.md", "config.json", "fixtures", "src"]}

Assistant:
Thought: The directory contains README.md, config.json, a fixtures
folder, and a src folder. I can now report these entries.
Final Answer: The current project directory contains the following entries:
README.md, config.json, fixtures, and src.
```

That's one Thought → Action → Action Input → Observation → Final Answer cycle. Multi-step tasks chain several cycles together — the model uses the observation from one tool call to decide which tool to call next:

```text
User: Read the fixture file and identify the city, then check the weather for that city.

Assistant:
Thought: I need to find the fixture file first. Let me list the directory.
Action: list_directory
Action Input: {"path": "fixtures"}

Observation: {"entries": ["city.txt", "codename.txt"]}

Thought: The fixtures directory contains city.txt. I'll read it to find
which city to look up.
Action: read_file
Action Input: {"path": "fixtures/city.txt"}

Observation: {"content": "Berlin"}

Thought: The file says Berlin. Now I need to call get_weather for Berlin.
Action: get_weather
Action Input: {"location": "Berlin"}

Observation: {"temperature": 18.5, "unit": "celsius", "condition": "partly cloudy"}

Final Answer: The weather in Berlin is 18.5°C with partly cloudy skies.
```

Two tool calls, each triggered by reasoning about the previous observation. That's the ReAct loop — and it's what the benchmark scores. A model that emits valid Thought/Action/Action Input lines and uses observations correctly scores high. A model that skips the reasoning, mangles the JSON, or ignores the observation gets a specific failure reason instead.

The protocol is deliberately text-based rather than using native function-calling APIs. This makes it universal — any model that can follow text instructions can in principle do ReAct, regardless of whether its runtime supports OpenAI-style function calling. The trade-off is that the model must *format* its output precisely: a stray colon, a missing JSON brace, or a tool name typo breaks the parse. This is why `INVALID_TOOL_SYNTAX` is one of the most common failure reasons — it's the format-compliance tax that ReAct imposes on smaller models.

### The Capability Ladder

Tasks are organized along a capability ladder that maps increasing agent sophistication:

| Level | Capability | Example Task |
|-------|-----------|-------------|
| 0 | Plain answer | Answer a static factual prompt |
| 1 | Recognizes missing context | Says a directory or weather tool is needed |
| 2 | Emits a valid tool call | Calls `list_directory` with valid JSON args |
| 3 | Uses tool output correctly | Names actual files returned by the tool |
| 4 | Multi-step tool use | Reads a file found by listing a directory |
| 5 | Error recovery | Retries after a bad path or failed request |
| 6 | Web/search grounding | Searches live information and cites the result |
| 7 | Browser navigation | Opens pages, follows links, extracts an answer |
| 8 | End-to-end agent work | Completes a small task with planning and tools |

The current benchmark suite covers levels 2–5 with two benchmark files: `smoke.json` (5 tasks) and `agentic.json` (5 tasks). Higher levels are planned.

### The Smoke Benchmark

The smoke benchmark is the entry point. Its five tasks test the foundations of tool use:

1. **Current directory** — Call `get_cwd` and report the path. Tests whether the model can emit a zero-argument tool call and use the result.

2. **List project** — Call `list_directory` with `{"path": "."}` and report the entries. Tests argument formatting and result utilization.

3. **Read fixture** — Call `read_file` with a specific path and extract a codename from the file content. Tests whether the model goes straight for the file or wastes steps exploring.

4. **Weather lookup** — Call `get_weather` for Berlin and report the temperature. Tests tool selection and result extraction from a live API response.

5. **Multi-step read then weather** — Read the fixture file, identify Berlin as the location, then call `get_weather` for Berlin. Tests tool chaining: the model must use the output of one tool call as input to a second, different tool call.

### The Agentic Benchmark

The agentic benchmark adds friction. Its five tasks test recovery, grounding, synthesis, and discipline:

1. **Recovery from bad path** — The model is told to read a file that doesn't exist. It must detect the failure, list the directory to find the correct file, read it, and report a recovery code. This is the only task that explicitly requires an error → recovery → success sequence.

2. **Grounding over prior knowledge** — The model reads a file stating the deployment color is "teal" and must answer only with that value, not "blue" or "green" which might be more common answers. Tests whether the model grounds its answer in tool output rather than prior training.

3. **Two-file synthesis** — Read two separate files and combine facts from both into a single answer (project codename + release window). Tests multi-call synthesis.

4. **Tool discipline** — Fetch weather for Berlin using only the weather tool, while filesystem tools are also available but forbidden for this task. Tests tool selection restraint.

5. **Conditional branching** — Read a file that specifies which city to use, then call `get_weather` for that city. Similar to the smoke multi-step task but with a branching condition that requires reading before deciding.

### Failure Reasons

Every task that doesn't pass gets a failure reason from a controlled vocabulary:

- **NO_TOOL_ATTEMPT** — The model returned a final answer without calling any tools.
- **INVALID_TOOL_SYNTAX** — The model attempted a tool call but didn't follow the Action/Action Input format.
- **WRONG_TOOL** — The model called a tool that wasn't in the allowed list for this task.
- **BAD_ARGUMENTS** — The tool was called with invalid arguments.
- **TOOL_EXECUTION_FAILED** — The tool itself errored (e.g., file not found).
- **IGNORED_TOOL_RESULT** — The tool returned data, but the model's final answer didn't incorporate it.
- **MISSING_REQUIRED_TOOL** — The task required a specific tool that was never called.
- **FORBIDDEN_TOOL** — The model called a tool explicitly forbidden for this task.
- **HALLUCINATED_RESULT** — The model reported data that wasn't in any tool result.
- **ASSERTION_FAILED** — Tools were called correctly, but the final answer didn't meet content assertions.
- **RUNTIME_ERROR** — The runtime adapter itself failed (not a model failure).
- **TIMEOUT** — The model didn't respond within the timeout window.
- **CONTEXT_LOSS** — The model returned an empty response after a tool observation.

This vocabulary is the heart of the benchmark. A score of 0.25 with `WRONG_TOOL` tells you something completely different from 0.25 with `MISSING_REQUIRED_TOOL` — the first is a tool-selection problem, the second is a multi-step planning problem.

## Runtime Adapters

Local Agent Bench doesn't just test models in isolation. It tests models *through* runtime adapters, because in practice nobody runs a raw Ollama API loop in production. The current adapters are:

- **raw-ollama-react** — Direct Ollama HTTP API calls with the ReAct prompt. This is the pure model baseline. It passes `temperature=0.0` by default, making it deterministic.

- **openclaw-react** — Uses OpenClaw's `infer model run --local --json` stateless inference path. The model gets OpenClaw's prompt structuring but no session context, workspace tools, or agent loop.

- **hermes-react** — Uses Hermes's `chat --query --quiet --ignore-rules` path. Hermes runs with a safe toolset and no user memory or project instructions.

- **pi-react** — Uses Pi's `--print` mode with all context stripped (`--no-tools`, `--no-context-files`, `--no-skills`, `--no-prompt-templates`, `--no-extensions`, `--offline`). This is the most stripped-down adapter.

- **openclaw-native** — Runs `openclaw agent --local --json`, a full agent session with workspace context, skills, and tool schemas. Tests OpenClaw's real platform tool-calling layer.

- **hermes-native** — Runs `hermes chat --query --quiet --ignore-rules --max-turns 1` with Hermes's safe toolset. Tests Hermes's real platform tool-calling layer.

- **pi-native** — Runs `pi --print --no-session --mode text` with Pi's native tools active (bash, read, write, edit). Tests Pi's real platform tool-calling layer.

The ReAct adapters all use the same benchmark tasks, the same harness-owned tools, and the same scoring logic. That makes cross-runtime comparison fair. The native adapters are used in two ways: strict tool-call compatibility tests, and the new `platform_native.json` use-case suite. As documented in [article-3](article-3-native-adapters.md), these reveal real platform constraints across all five benchmark models: context overflow, model-override rejection, silent session failure, toolset misconfiguration, tool registration gaps, and the difference between tool-call syntax and user-visible completion.

### ReAct vs Native Tool Calling

Because the benchmark includes both ReAct adapters and native adapters for the same models, you can directly measure how much of a model's failure is format compliance versus reasoning. The difference matters:

With **ReAct**, the model must hand-format every tool call as text — `Thought:`, `Action:`, `Action Input: {"path": "."}` — and the harness parses that text. Smaller models frequently mangle this: a missing colon, a broken JSON brace, a tool name typo. Each of these produces an `INVALID_TOOL_SYNTAX` failure. The model may have correctly reasoned about *which* tool to call and *what* arguments to pass, but it still scores 0 because the format was wrong.

With **platform-native use cases**, the benchmark no longer forces the model to call `get_weather` or `list_directory`. The runtime can use platform tools such as Pi's `bash` or `read`, OpenClaw's tools, or Hermes toolsets. This removes the ReAct formatting tax — *if the platform supports the model and exposes useful tools*. The task prompt asks for an evidence line naming the command or tool used and the relevant output, then an LLM judge evaluates whether the response actually completed the task.

But native calling doesn't fix everything. Failures like `IGNORED_TOOL_RESULT` (the tool returned data but the model didn't use it) and `HALLUCINATED_RESULT` (the model invented data that wasn't in the observation) stay roughly the same. These are reasoning problems, not format problems. If the model doesn't pay attention to the observation, switching from ReAct to native calling doesn't help.

This is why the benchmark reports native results in two layers: strict protocol compatibility and platform-native task completion. The strict score tells you whether benchmark tools are wired into the platform. The platform-native use-case score tells you whether the platform response was actually useful. In practice, the native adapters currently serve as **platform diagnostics** rather than pure model rankings — they tell you which platforms work with which models, not just which model is best.

## Hardware and Reproducibility

The benchmark is designed to be reproducible on different hardware. Results should always include:

- Machine model and GPU/VRAM
- OS and Ollama version
- Model name and quantization level
- Runtime adapter
- Benchmark commit SHA

All results in this article were generated on:

- **Machine:** Lenovo ThinkPad P14s Gen 6
- **CPU:** Intel Core Ultra 7 265H
- **RAM:** 32 GB
- **GPU:** NVIDIA RTX PRO 1000 Blackwell, 8 GB VRAM
- **OS:** WSL2 Ubuntu 24.04
- **Ollama:** 0.31.1

The harness redacts local paths (`<PROJECT_ROOT>`, `<HOME>`) in output JSON, so results can be shared without leaking filesystem structure.

## The Diagnostic Layer System

The benchmark's failure vocabulary is organized by diagnostic layer — the part of the stack where the failure actually occurred. This is what makes the benchmark diagnostic rather than just evaluative:

| Layer | Failure Reasons | What It Means |
|-------|---------------|---------------|
| **Tool protocol** | `INVALID_TOOL_SYNTAX`, `NO_TOOL_ATTEMPT` | The model can't follow the ReAct format or doesn't recognize that tools are needed. This is a model/prompt issue. |
| **Tool selection** | `WRONG_TOOL`, `FORBIDDEN_TOOL`, `BAD_ARGUMENTS` | The model can emit tool calls but picks the wrong tool or passes wrong arguments. This is a model reasoning issue. |
| **Tool execution** | `TOOL_EXECUTION_FAILED` | The tool itself errored — file not found, network down, invalid input. This is an environment issue, not a model issue. |
| **Agent loop** | `IGNORED_TOOL_RESULT`, `HALLUCINATED_RESULT`, `MISSING_REQUIRED_TOOL`, `CONTEXT_LOSS` | The tool worked, but the model didn't use the result correctly. This is a model attention/planning issue. |
| **Runtime** | `RUNTIME_ERROR`, `RUNTIME_UNAVAILABLE`, `TIMEOUT` | The adapter itself failed — CLI crashed, wrong output stream, model not found. This is a runtime/infrastructure issue. |

When you see a model score 0/5 with all `RUNTIME_ERROR` failures, the model is fine — the adapter is broken. When you see `INVALID_TOOL_SYNTAX` across all tasks, the model needs a different prompting strategy. When you see `IGNORED_TOOL_RESULT`, the model called the tool successfully but couldn't integrate the observation into its reasoning. Each layer suggests a different fix.

This layer separation is the benchmark's core contribution. Without it, a runtime adapter bug looks like a model failure, a network outage looks like a tool-use deficit, and a prompt-format mismatch looks like a reasoning limitation. With it, you know exactly where to look.

## The Temperature Problem

One of the most important findings from this benchmark work is that temperature control across runtimes is inconsistent. The `raw-ollama-react` adapter explicitly passes `temperature=0.0` to Ollama, producing deterministic, greedy decoding. The other three adapters — `openclaw-react`, `hermes-react`, `pi-react` — all ignore the temperature parameter (`del temperature` in their code) and use whatever default their CLI tools ship with, which is typically >0.

This means that `raw-ollama-react` results are perfectly reproducible across runs — the same tasks pass and fail every time, with the same failure reasons and nearly identical latencies. The other runtimes are probabilistic: a single run can show 0/5 or 3/5 depending on sampling luck, and you need multiple runs to get a meaningful picture.

This is not a bug — the benchmark intentionally lets each runtime use its own configuration, because that's the real-world experience. If you deploy agents through OpenClaw, you get OpenClaw's defaults. If you deploy through Hermes, you get Hermes's defaults. The benchmark should reflect that reality, not impose an artificial temperature that no production system would use.

But it means that any benchmark methodology must account for variance, or it will produce misleading rankings. A single run of hermes-react on the agentic benchmark can return 0/5 or 3/5 — if you only run it once, you might conclude the model is useless when it's merely inconsistent.

## Statistical Methodology

The recommended number of runs per runtime depends on the observed variance:

- **raw-ollama-react:** 1 run (deterministic, temperature=0)
- **openclaw-react:** 3 runs (very stable, low variance)
- **hermes-react:** 10 runs for the agentic benchmark, 3 for smoke (high variance on agentic tasks)
- **pi-react:** 12 runs for agentic, 6 for smoke (highest variance)

These numbers were projected from 3-run pilot data using standard sample-size formulas: N = (z × σ / E)², where E is the desired margin of error (±1.0 point at 95% confidence). With these sample sizes, the 95% confidence intervals become tight enough to distinguish runtime performance with reasonable certainty.

All runs must be sequential — never parallel. Running multiple benchmarks simultaneously against the same Ollama instance causes GPU resource contention, which inflates latency and can even affect output quality if the model is slow enough to hit timeout boundaries. The difference is not subtle: a model that scores 4/5 when run alone can drop to 1/5 when three benchmarks compete for the same GPU.

## Anatomy of a Benchmark Run

When you launch a benchmark run, the harness executes the following sequence for each task:

1. **Preflight** — The `diagnose` command checks every layer before any task runs: Python version, Ollama CLI and API reachability, model availability, filesystem tool correctness, and network access to Open-Meteo. If Ollama is unreachable, you get `OLLAMA_UNREACHABLE` — not a confusing model failure. If the weather API is down, you get a network-layer diagnostic — not a model that "can't do weather."

2. **System prompt injection** — The harness constructs a system prompt listing all available tools with their names, descriptions, and argument schemas. The model is told to use exactly one of two formats: `Thought → Action → Action Input` (for tool calls) or `Final Answer:` (for completion).

3. **ReAct loop** — For each task, the harness sends the system prompt + user task prompt to the model. If the model emits a tool call, the harness executes the tool locally, wraps the result as `Observation: {json}`, and appends it to the transcript. The model gets the observation and can either call another tool or give a final answer. The loop runs for up to `max_steps` iterations (default 5).

4. **Scoring** — Once the model emits a Final Answer (or runs out of steps), the harness evaluates assertions. These can check:
   - Whether the final answer contains specific values
   - Whether the tool result contains expected data
   - Whether required tools were called
   - Whether forbidden tools were avoided
   - Whether tools were called in the right sequence
   - Whether the answer contains values from the tool result (not hallucinated)

5. **Output** — Every task result is saved as JSON with: the full transcript (system prompt, user prompt, assistant responses, tool observations), every tool call with its arguments and result, the score, the failure reason, assertion-level details, latency, and model metadata (family, parameter size, quantization, architecture details from Ollama).

This structure means you can always trace *why* a task failed. The transcript shows exactly what the model said, what the tool returned, and what the model did with that information. You don't have to guess.

### Redaction and Privacy

The harness automatically redacts local paths in output files. The project root becomes `<PROJECT_ROOT>` and the home directory becomes `<HOME>`. This means you can share result JSON files publicly without leaking your filesystem structure. Model metadata (including Ollama version, model architecture, quantization) is preserved because it is essential for reproducibility.

### CLI Adapter Overrides

Different machines may have runtime CLIs installed in different locations. The benchmark supports environment variable overrides:
- `LOCAL_AGENT_BENCH_OPENCLAW_BIN` — path to the OpenClaw binary
- `LOCAL_AGENT_BENCH_HERMES_BIN` — path to the Hermes binary
- `LOCAL_AGENT_BENCH_PI_COMMAND` — full Pi command (useful for `npx` invocation)
- `LOCAL_AGENT_BENCH_OPENCLAW_THINKING` — enable thinking mode for OpenClaw inference
- `LOCAL_AGENT_BENCH_HERMES_TOOLSETS` — configure Hermes tool access

These overrides ensure the benchmark can run in diverse environments without code changes.

## What the Benchmark Does Not Cover

Local Agent Bench is deliberately small and focused. It does not:

- Test coding ability (no code generation tasks)
- Test long-context reasoning (all tasks fit in a few thousand tokens)
- Test browser navigation or web search (planned for levels 6–7)
- Test multi-turn conversation (each task is a single ReAct loop)
- Compare against hosted frontier models (planned as a `baseline` adapter)
- Test API-level function calling in isolation. The native adapters test real CLI/platform loops, not OpenAI-style function-call APIs directly.
- Prove tool execution when a platform hides tool traces from stdout. The platform-native suite asks for evidence and judges it, but opaque CLIs still require caution.

These limitations are intentional. The benchmark's value is diagnostic precision, not breadth. A model that scores 5/5 on the smoke benchmark and 5/5 on the agentic benchmark has demonstrated that it can follow a ReAct protocol, call the right tools with valid arguments, chain tool calls across multiple steps, recover from errors, and ground its answers in observed data. That is the foundation everything else is built on.

## Getting Started

The benchmark is open source and runs on any machine with Python 3.11+, Ollama, and at least one installed model:

```bash
git clone https://github.com/ebelo/local-agent-bench.git
cd local-agent-bench
python3 -m local_agent_bench diagnose
python3 -m local_agent_bench run --model mistral:7b
```

The `diagnose` command checks your environment layer by layer: Python version, Ollama reachability, model availability, filesystem tools, and network access to the weather API. Any failures are reported with their layer, so you can fix configuration before running the actual benchmark.

Results are saved as JSON files with full transcripts, tool call logs, assertion details, and model metadata. They are designed to be diffed, compared, and aggregated — not just read as a single number.

## Conclusion

Local Agent Bench exists because the local LLM ecosystem needed honest instrumentation. When a 7B model fails to call a tool, the question isn't "can this model use tools?" — it's "which layer broke?" The benchmark answers that question with a controlled vocabulary of failure reasons, comparable across models, runtimes, and hardware. And by respecting the statistical nature of non-deterministic runtimes, it produces rankings you can actually trust.

The next frontier is higher capability levels — web grounding, browser navigation, and end-to-end agent work. But the foundation is here: a fair, diagnostic, reproducible benchmark that tells you not just *whether* your local agent failed, but *where* and *why*.
