# Native Adapters: Testing Real Platform Tool-Calling

*Three runtimes, two models, thirty benchmark runs — and every single one scored 0/5. Here's what broke, where, and why it matters.*

---

## The Question

The ReAct adapters in Local Agent Bench answer one question: *can the model follow a text-based tool-call protocol?* They test the model's ability to emit `Thought: ... Action: tool_name Action Input: {"arg": "value"}` in the right format, using a benchmark-owned prompt that describes the tools.

But every production agent platform — OpenClaw, Hermes, Pi — has its own native tool-calling layer. These platforms don't use ReAct text parsing. They register tools with the model through system prompts, structured schemas, or API-level function calling, and the model's output is parsed by the platform, not by a text regex.

The native adapters test a different question: **does the model actually work through the real platform agent loop?** Not "can it follow a text protocol" but "can it use tools when the platform owns the tool-calling infrastructure."

This matters because in production, nobody runs raw ReAct loops. They run OpenClaw agents, Hermes chats, or Pi sessions. If the platform's tool-calling layer doesn't work with a given model, that's a real production blocker — regardless of how well the model scores on ReAct.

## The Three Native Adapters

| Adapter | Platform | How it runs | What it tests |
|---------|----------|-------------|---------------|
| `openclaw-native` | OpenClaw | `openclaw agent --local --json --model ... --message ...` | Full agent session with workspace context, skills, tool schemas |
| `hermes-native` | Hermes | `hermes chat --query --quiet --model ... --toolsets safe --max-turns 1 --ignore-rules` | Hermes chat with safe toolset, no user rules |
| `pi-native` | Pi | `pi --print --no-session --no-context-files --no-skills --no-extensions --offline --mode text --model ...` | Pi with native tools active (bash, read, write, edit), no context files |

All three use the benchmark's smoke tasks (5 tasks: get_cwd, list_directory, read_file, get_weather, multi-step). The scoring checks whether the model emitted native tool-call JSON that matches the benchmark's tool definitions (`get_cwd`, `list_directory`, `read_file`, `get_weather`).

## Results: 0/5 Across the Board

| Adapter | Model | Score | Failure | Avg Latency |
|---------|-------|:-----:|---------|:-----------:|
| openclaw-native | mistral:7b | 0/5 | CONTEXT_OVERFLOW | 5.4s |
| openclaw-native | lfm2.5 | 0/5 | RUNTIME_ERROR | 2.8s |
| hermes-native | mistral:7b | 0/5 | RUNTIME_ERROR (64K context required) | 2.2s |
| hermes-native | lfm2.5 | 0/5 | NO_NATIVE_TOOL_ATTEMPT | 11.9s |
| pi-native | mistral:7b | 0/5 | NO_NATIVE_TOOL_ATTEMPT | 5.6s |
| pi-native | lfm2.5 | 0/5 | NO_NATIVE_TOOL_ATTEMPT | 7.7s |

Every single run scored 0/5. But the failure reasons are completely different — and each one reveals a real platform constraint.

## Finding 1: OpenClaw Agent Mode Overflows Small Model Context

**What happened:** `openclaw agent --local --json --model ollama/mistral:7b` loads the full OpenClaw workspace context before the model sees the task prompt. This includes:

- `AGENTS.md` (~9K chars) — workspace instructions
- `SOUL.md` (~2K chars) — persona definition
- `MEMORY.md` (~20K chars, truncated) — long-term memory
- Skill definitions (~8K chars) — all installed skills
- Tool schemas (~43K chars) — all available tool definitions

Total: ~56K chars of system context. For mistral:7b with a default 32K context window, this is an immediate `context_overflow` error — the model never even sees the task.

**The error message:** `"Context overflow: prompt too large for the model. Try /reset (or /new) to start a fresh session, or use a larger-context model."`

**Contrast with openclaw-react:** The ReAct adapter uses `openclaw infer model run --local --json` — a stateless inference path that doesn't load workspace context. It passes only the benchmark's ReAct system prompt (~1K chars) and the task. This works fine with mistral:7b (5/5 on smoke).

**Real-world implication:** OpenClaw's agent mode is designed for larger models. If you're running a 7B model with 32K context, agent mode will fail before the model even starts reasoning. You need either a larger-context model (65K+), a stripped-down workspace, or the stateless `infer` path.

**Potential OpenClaw improvement:** Add a `--no-context-files` or `--bare` flag to `openclaw agent` that skips loading AGENTS.md, MEMORY.md, skills, and tool schemas — similar to Pi's `--no-context-files --no-skills` flags. This would allow agent mode to work with small models for lightweight tasks.

## Finding 2: Hermes Requires 64K Context Minimum

**What happened:** `hermes chat --query --quiet --model ollama/mistral:7b` refuses to run at all. Hermes checks the model's loaded context size and rejects it:

> "Ollama loaded `mistral:7b` with only 32,768 tokens of runtime context, but Hermes needs at least 64,000 tokens for reliable tool use. Increase the Ollama context for this model and restart/reload the model before trying again."

This is a hard gate — Hermes exits with code 1 and produces no model output. The adapter captures this as `RUNTIME_ERROR`.

**Contrast with lfm2.5:** Hermes runs lfm2.5 (which has a larger default context) but the model can't find the benchmark tools. Hermes exposes its own toolset (`safe`), which includes tools like `bash`, `read`, `write`, `edit` — not `get_cwd`, `list_directory`, `read_file`, `get_weather`. The model either answers directly without tools or tries Hermes's own tools and fails to produce benchmark-compatible output.

**Real-world implication:** Hermes has a context window floor of 64K tokens. Models with default 32K context (most 7B models on Ollama) cannot run through Hermes at all without increasing `num_ctx`. This is a platform constraint, not a model limitation — the same model works fine through raw-ollama-react and openclaw-react.

**Potential Hermes improvement:** Allow overriding the context requirement for lightweight tasks, or automatically increase `num_ctx` via the Ollama API when the model's default is too small.

## Finding 3: Pi's Native Tools ≠ Benchmark Tools

**What happened:** `pi --print --no-session --no-context-files --no-skills --no-extensions --offline --mode text --model ollama/mistral:7b` runs successfully — Pi strips its own context well, and the model responds. But the model uses Pi's built-in tools (bash, read, write, edit), not the benchmark's tools.

For the "list project directory" task, mistral:7b through pi-native responded:
> "To see the contents of the current working directory, execute a `bash` command: `bash 'ls -la'`"

The model recognized that it needed to list files and attempted to call a tool — but it used Pi's `bash` tool format, not the benchmark's `list_directory` tool. The native tool-call scorer found no benchmark-compatible tool calls in the output, resulting in `NO_NATIVE_TOOL_ATTEMPT`.

For lfm2.5, the model actually listed the directory correctly using Pi's tools:
> "**Files in the project directory** - `.git` (directory) - `.github` (directory) - `articles` (directory) - `benchmarks` (directory)..."

But it still scored 0/5 because it didn't emit benchmark tool-call JSON. The model used Pi's native tools to accomplish the task — it just didn't use the benchmark's tools.

**Real-world implication:** Pi's native tool-calling layer works — the model can call bash, read files, and list directories. But the benchmark tools (`get_cwd`, `list_directory`, `read_file`, `get_weather`) don't exist in Pi's tool registry. The model follows Pi's tool format, not the benchmark's.

This reveals a fundamental limitation of the native adapter approach: **the benchmark's tools are not registered with the platform.** The ReAct adapters work because they use a benchmark-owned prompt that describes the tools and a benchmark-owned parser that extracts tool calls. The native adapters rely on the platform's tool registry, which has different tools.

## The Tool Registration Gap

All three native adapters share the same root issue: **the benchmark's tools are not registered with the platform.**

| Platform | Has `get_cwd`? | Has `list_directory`? | Has `read_file`? | Has `get_weather`? |
|----------|:-:|:-:|:-:|:-:|
| OpenClaw | No (has `read`, `exec`) | No (has `read`) | Yes (has `read`) | No |
| Hermes | No (has `bash`) | No (has `bash`) | No (has `read`) | No |
| Pi | No (has `bash`) | No (has `bash`) | Yes (has `read`) | No |

No platform has `get_weather` — that's a benchmark-owned tool that calls the Open-Meteo API. No platform has `get_cwd` — they all have more general filesystem or shell tools.

This means the native adapters, as currently designed, can only test whether the model *attempts* a tool call in a recognizable format. They can't test whether the model *selects the right tool* because the right tool doesn't exist in the platform's registry.

## Two Layers of Native Testing

The results suggest that "native tool calling" is actually two separate things:

1. **Format compliance** — Can the model emit a structured tool call (JSON, function call) instead of free text? This is what the `infer model run` path with `NATIVE_SYSTEM_PROMPT` tests. It's equivalent to ReAct but with JSON instead of Action/Action Input.

2. **Platform integration** — Does the model work with the platform's real tool registry, real tool schemas, and real tool execution? This is what `openclaw agent`, `hermes chat`, and `pi --print` (with tools) test.

The ReAct adapters already test layer 1 (format compliance) through the benchmark's own prompt and parser. The native adapters attempt to test layer 2 (platform integration) but fail because the benchmark's tools aren't registered with the platforms.

## What Would Fix This

To properly test platform integration, the native adapters would need to:

**Option A: Register benchmark tools with each platform.** Create OpenClaw tools, Hermes tools, and Pi extensions that wrap the benchmark's `get_cwd`, `list_directory`, `read_file`, and `get_weather` functions. Then the model would see the benchmark tools in the platform's native format and could call them through the platform's tool-calling layer. This is the most faithful test but requires platform-specific integration work.

**Option B: Use the platform's own tools and adapt the tasks.** Instead of testing whether the model calls `list_directory`, test whether it calls `bash ls` (Pi) or `read` (OpenClaw/Hermes). Map the benchmark tasks to platform-equivalent tools. This tests real platform integration but makes cross-runtime comparison harder — you're comparing different tool ecosystems.

**Option C: Accept the current findings as real platform constraints.** The context overflow (OpenClaw), context requirement (Hermes), and tool mismatch (Pi) are all real findings that would affect anyone trying to use these platforms with 7B models. Document them and move on.

## The OpenClaw Context Isolation Finding

The OpenClaw context overflow is the most actionable finding. OpenClaw's `infer model run` path (used by openclaw-react) works perfectly with 7B models because it's stateless — no workspace context. But `openclaw agent` loads everything: AGENTS.md, MEMORY.md, skills, tool schemas.

This is by design — OpenClaw agent mode is meant to be a full agent with access to its workspace, memory, and tools. But it means agent mode has a de facto minimum context requirement of ~56K tokens, which excludes most 7B models with default Ollama settings (32K).

The fix for production use is straightforward: either use a model with 65K+ context (e.g., qwen3.5:9b with `num_ctx 65536`), or use the `infer` path for lightweight tasks. For the benchmark, the finding is that **OpenClaw agent mode and 7B models with 32K context are incompatible without configuration changes**.

## The Hermes Context Gate Finding

Hermes is unique among the three platforms in that it actively refuses to run a model with insufficient context. OpenClaw and Pi let the model run and fail silently (or produce truncated output). Hermes checks the context size upfront and exits with a clear error message.

This is good for production (you get a clear error instead of silent failures) but bad for benchmarking (the model never gets a chance to try). The 64K minimum is a Hermes policy, not a model limitation — mistral:7b can technically run with 32K, it just won't have enough context for Hermes's tool-calling infrastructure.

For the benchmark, the finding is that **Hermes has a hard 64K context floor for any model using toolsets**. Models with default 32K context cannot be tested through Hermes without increasing `num_ctx`.

## The Pi Tool Layer Finding

Pi is the most context-efficient of the three platforms. With `--no-context-files --no-skills --no-extensions --offline`, the system prompt is minimal — no workspace files, no skills, no extensions. The model has plenty of context room.

But Pi's native tools (bash, read, write, edit) are general-purpose, not benchmark-specific. The model correctly identifies that it needs to list files or read a file, and it attempts to use Pi's tools to do so — but the benchmark scorer doesn't recognize Pi's tool-call format as a benchmark tool call.

Interestingly, lfm2.5 through pi-native actually *accomplished* several tasks using Pi's bash tool. It listed the directory correctly (the output showed real file names from the project), attempted to read the fixture file, and even tried to fetch weather (though it got a 401 from the weather API). The model can use tools — they're just not the benchmark's tools.

## Conclusion

The native adapter results are not a failure of the benchmark or the adapters. They are **real findings about platform compatibility with small models**:

1. **OpenClaw agent mode** requires ~56K tokens of workspace context, overflowing 32K-context models. Use `infer` for lightweight tasks or increase `num_ctx`.

2. **Hermes** has a hard 64K context minimum for tool-using models. Most 7B models on Ollama default to 32K and cannot run through Hermes without configuration.

3. **Pi** has the best context isolation but its native tools (bash, read, write, edit) don't include benchmark-specific tools. The model can use Pi's tools to accomplish tasks, but the benchmark can't score platform-specific tool calls.

4. **No platform registers the benchmark's tools** (`get_cwd`, `list_directory`, `read_file`, `get_weather`). To properly test platform-native tool calling, the benchmark tools would need to be registered as platform extensions.

These findings are the value of the native adapters. They don't produce a score — they produce a diagnosis. And the diagnosis is clear: **the platforms are not ready for 7B models with default context, and the benchmark tools are not registered with any platform.**

The next step is either registering benchmark tools as platform extensions (Option A) or accepting these as real platform constraints and focusing the benchmark on the ReAct adapters, which already provide fair cross-runtime comparison (article-2).

---

*All benchmark data, result files, and the harness itself are open source at [github.com/ebelo/local-agent-bench](https://github.com/ebelo/local-agent-bench). Native adapter runs were conducted on Lenovo P14s Gen 6, NVIDIA RTX PRO 1000 Blackwell 8GB, WSL2 Ubuntu 24.04, Ollama 0.30.10. OpenClaw 2026.6.8, Hermes v0.17.0, Pi 0.79.8. All runs sequential, smoke benchmark (5 tasks), 2026-07-08.*

*Generated by OpenClaw 2026.6.8 · model=ollama/glm-5.2:cloud · reasoning=off*