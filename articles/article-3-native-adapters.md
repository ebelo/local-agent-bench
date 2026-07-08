# Native Adapters: Testing Real Platform Tool-Calling

*Three runtimes, five models, forty-five benchmark runs — and almost every single one scored 0/5. Here's what broke, where, and why it matters.*

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

All three use the benchmark's smoke tasks (5 tasks: get_cwd, list_directory, read_file, get_weather, multi-step). There are now two scoring layers:

1. **Strict native tool-call score**: checks whether the model emitted structured tool-call JSON matching the benchmark's tool definitions (`get_cwd`, `list_directory`, `read_file`, `get_weather`).
2. **LLM-as-judge task-completion score**: uses OpenClaw `infer` with `ollama/glm-5.2:cloud` to evaluate whether the platform response actually accomplished the task intent, even when it used platform-native tools like Pi's `bash` or `read`.

The second score was added after a manual Pi session with Ornith:9b showed the problem clearly: Ornith used `bash` to fetch live weather from `wttr.in` and answered correctly, but the strict scorer still gave 0/5 because it did not emit benchmark-specific `get_weather` JSON.

## The Five Models

| Model | Family | Size | Context (default) | ReAct ranking |
|-------|--------|------|:-:|--------|
| qwen2.5-coder:7b | Qwen2.5 | 7.6B | 32K | #1 overall (5/5 smoke, perfect speed) |
| qwen3.5:9b | Qwen3.5 | 9.0B | 40K | #2 (4/5 agentic, strongest reasoning) |
| Ornith:9b | Qwen3.5 (Ornith-1.0) | 9.0B | 40K | #3 (best grounding, reliable) |
| mistral:7b | Mistral | 7.2B | 32K | #4 (protocol-compliant, fast on raw) |
| lfm2.5:latest | Jamba (MoE) | 8.5B | 256K | #5 (fast but poor ReAct compliance) |

These are the five models that produced the ReAct rankings in article-2. Testing them natively answers: *do the ReAct rankings predict platform-native performance?*

## Strict Results: 14/15 Cells at 0/5

| Adapter | Model | Strict Score | Root Cause | Avg Latency |
|---------|-------|:------------:|------------|:-----------:|
| openclaw-native | mistral:7b | 0/5 | Context overflow (56K workspace vs 32K window) | 5.4s |
| openclaw-native | lfm2.5:latest | 0/5 | Model override rejected by OpenClaw | 2.8s |
| openclaw-native | qwen3.5:9b | 0/5 | Model override rejected by OpenClaw | 2.7s |
| openclaw-native | qwen2.5-coder:7b | 0/5 | Context overflow (56K workspace vs 32K window) | 5.3s |
| openclaw-native | ornith:9b | 0/5 | Model override rejected by OpenClaw | 2.7s |
| hermes-native | mistral:7b | 0/5 | Hermes silent failure (32K context, session only) | 2.2s |
| hermes-native | lfm2.5:latest | 0/5 | Tool mismatch (Hermes tools != benchmark tools) | 11.9s |
| hermes-native | qwen3.5:9b | 0/5 | Tool mismatch (only `vision_analyze` available) | 18.3s |
| hermes-native | qwen2.5-coder:7b | 0/5 | Hermes silent failure (32K context, session only) | 2.2s |
| hermes-native | ornith:9b | 0/5 | Tool mismatch (only `vision_analyze` available) | 14.7s |
| pi-native | mistral:7b | 0/5 | Tool mismatch (Pi tools != benchmark tools) | 5.6s |
| pi-native | lfm2.5:latest | 0/5 | Tool mismatch (Pi tools != benchmark tools) | 7.7s |
| pi-native | qwen3.5:9b | 0/5 | Tool mismatch (Pi tools != benchmark tools) | 20.9s |
| **pi-native** | **qwen2.5-coder:7b** | **1.5/5** | **Emitted parseable JSON tool calls; one `read` alias matched `read_file`** | **3.8s** |
| pi-native | ornith:9b | 0/5 | Tool mismatch (Pi tools != benchmark tools) | 17.5s |

Fourteen out of fifteen cells scored 0/5. The one non-zero result — qwen2.5-coder:7b through pi-native — scored 1.5/5: a perfect `read_file` call (1.0), a `bash` call instead of `list_directory` (0.25), and a `bash` call instead of `get_weather` (0.25).

That strict result is useful, but incomplete. It measures benchmark-tool protocol compatibility, not whether the platform session actually helped the user.

## LLM-Judged Task Completion Results

The LLM judge evaluates the final platform response flexibly: did the agent actually accomplish the user's task, using any real platform tool? This flips the Pi results:

| Adapter | mistral:7b | lfm2.5 | qwen3.5:9b | qwen2.5-coder:7b | ornith:9b | Interpretation |
|---------|:---------:|:------:|:----------:|:----------------:|:--------:|----------------|
| openclaw-native | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | Still blocked by context overflow or model override |
| hermes-native | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | Still blocked by silent sessions or unavailable tools |
| pi-native | 1/5 | 1.5/5 | **3/5** | 0/5 | **2/5** | Pi can accomplish tasks with platform tools, but not consistently |

The important correction: **Ornith:9b through Pi is not a real 0/5 user experience.** It listed the project directory and fetched current weather successfully, but strict scoring missed both because they were done through Pi's native `bash`/text flow instead of benchmark `list_directory`/`get_weather` JSON.

qwen3.5:9b was the strongest Pi-native task completer by judge score: it listed files, identified the benchmark codename, and answered current weather. Ornith:9b completed directory listing and weather. lfm2.5 completed directory listing and partially handled the multi-step task. mistral:7b got credit for current weather. qwen2.5-coder:7b is the inverse case: it emitted parseable tool-call JSON, which strict scoring rewarded, but the platform response did not complete the tasks as user-facing answers, so the judge gave it 0/5.

But the 0/5 results are not all the same. There are **four distinct failure modes**, each revealing a different platform constraint.

## Finding 1: OpenClaw Agent Mode Has Two Failure Modes

### 1a: Context Overflow (mistral:7b, qwen2.5-coder:7b)

**What happened:** `openclaw agent --local --json --model ollama/mistral:7b` loads the full OpenClaw workspace context before the model sees the task prompt. This includes:

- `AGENTS.md` (~9K chars) — workspace instructions
- `SOUL.md` (~2K chars) — persona definition
- `MEMORY.md` (~20K chars, truncated) — long-term memory
- Skill definitions (~8K chars) — all installed skills
- Tool schemas (~43K chars) — all available tool definitions

Total: ~56K chars of system context. For mistral:7b and qwen2.5-coder:7b, both with default 32K context windows, this is an immediate `context_overflow` error — the model never even sees the task.

**The error message:** `"Context overflow: prompt too large for the model. Try /reset (or /new) to start a fresh session, or use a larger-context model."`

**Contrast with openclaw-react:** The ReAct adapter uses `openclaw infer model run --local --json` — a stateless inference path that doesn't load workspace context. It passes only the benchmark's ReAct system prompt (~1K chars) and the task. This works fine with both models (mistral:7b scores 5/5 on smoke, qwen2.5-coder:7b scores 5/5).

### 1b: Model Override Rejected (lfm2.5, qwen3.5:9b, ornith:9b)

**What happened:** For lfm2.5:latest, qwen3.5:9b, and ornith:9b, OpenClaw rejected the `--model` flag entirely:

> `Error: Model override "ollama/qwen3.5:9b" is not allowed for agent "main".`

This is a **security policy**, not a context issue. OpenClaw's agent configuration restricts which models can be used for a given agent. The `main` agent is configured with a specific model, and the benchmark's `--model` override is blocked.

This is a different problem from the context overflow: the model never gets a chance to fail on context because OpenClaw refuses to switch to it in the first place. The fix is either allowing the model override in OpenClaw config or creating a dedicated benchmark agent that permits these models.

**Real-world implication:** OpenClaw's agent mode has a de facto minimum context requirement of ~56K tokens (excluding the model-override-gated models), which excludes most 7B models with default Ollama settings (32K). Additionally, the model-override security gate means that even models with sufficient context (like qwen3.5:9b at 40K or lfm2.5 at 256K) cannot be tested without configuration changes.

**Potential OpenClaw improvement:** Add a `--no-context-files` or `--bare` flag to `openclaw agent` that skips loading AGENTS.md, MEMORY.md, skills, and tool schemas — similar to Pi's `--no-context-files --no-skills` flags. This would allow agent mode to work with small models for lightweight tasks. Additionally, document the model-override policy and provide a way to whitelist benchmark models.

## Finding 2: Hermes Has Two Failure Modes for 32K Models

### 2a: Silent Session Failure (mistral:7b, qwen2.5-coder:7b)

**What happened:** `hermes chat --query --quiet --model ollama/mistral:7b` creates a session but produces no model output. The only response is a session ID:

> `session_id: 20260708_202233_5f7e45`

No error message, no model reasoning, no tool calls. Hermes v0.18.2 appears to accept the request but the model never generates. This is likely because both models have 32K default context and Hermes's tool-calling infrastructure requires more — but unlike the older Hermes v0.17.0 (which produced an explicit "64,000 tokens required" error), the new version silently produces an empty session.

**The earlier explicit rejection:** During initial testing with Hermes v0.17.0, mistral:7b produced a hard error:

> "Ollama loaded `mistral:7b` with only 32,768 tokens of runtime context, but Hermes needs at least 64,000 tokens for reliable tool use. Increase the Ollama context for this model and restart/reload the model before trying again."

Hermes v0.18.2 no longer emits this message. The 64K requirement still exists but the error is silent — the session is created, no output is produced, and the adapter sees only the session ID.

### 2b: Tool Mismatch (lfm2.5:latest, qwen3.5:9b, ornith:9b)

**What happened:** These three models have sufficient context to run through Hermes (lfm2.5 has 256K, qwen3.5:9b and ornith:9b have 40K). Hermes runs and the model responds — but it can't find the benchmark tools.

For qwen3.5:9b, the model reported:
> "I'm unable to list the directory contents because my available tools don't include `terminal` or file listing capabilities — only `vision_analyze`."

For ornith:9b:
> "I attempted to list the files and folders using `agent_list`, but that tool is unavailable (the only available tool is `vision_analyze`)."

Hermes exposed only `vision_analyze` as the available tool, not the safe toolset (`bash`, `read`, `write`, `edit`) that the benchmark expected. This suggests a Hermes configuration issue — the `--toolsets safe` flag may not be registering tools correctly in v0.18.2, or the tools are registered but the model only sees a subset.

For lfm2.5, the model answered directly without attempting any tool calls, producing correct text answers for some tasks (e.g., naming the working directory) but no benchmark-compatible tool calls.

**Real-world implication:** Hermes has a hard 64K context floor for tool-using models. Models with 32K context produce empty sessions silently. Models with sufficient context still fail because the benchmark tools aren't registered with Hermes — and in v0.18.2, even the safe toolset may not be properly exposed to the model.

**Potential Hermes improvement:** Restore the explicit context-too-small error message (v0.17.0 behavior) so users get a clear diagnosis instead of an empty session. Additionally, verify that `--toolsets safe` correctly registers all safe tools with the model.

## Finding 3: Pi's Tool Mismatch — and the One Partial Pass

**What happened:** `pi --print --no-session --no-context-files --no-skills --no-extensions --offline --mode text --model ollama/mistral:7b` runs successfully — Pi strips its own context well, and the model responds. But the model uses Pi's built-in tools (bash, read, write, edit), not the benchmark's tools.

For the "list project directory" task, mistral:7b through pi-native responded:
> "To see the contents of the current working directory, execute a `bash` command: `bash 'ls -la'`"

The model recognized that it needed to list files and attempted to call a tool — but it used Pi's `bash` tool format, not the benchmark's `list_directory` tool. The native tool-call scorer found no benchmark-compatible tool calls in the output, resulting in `NO_NATIVE_TOOL_ATTEMPT`.

For lfm2.5, the model actually listed the directory correctly using Pi's tools:
> "**Files in the project directory** - `.git` (directory) - `.github` (directory) - `articles` (directory) - `benchmarks` (directory)..."

But it still scored 0/5 because it didn't emit benchmark tool-call JSON. The model used Pi's native tools to accomplish the task — it just didn't use the benchmark's tools.

### The qwen2.5-coder:7b Exception

qwen2.5-coder:7b through pi-native was the **only model+adapter combination that produced a non-zero strict native tool-call score** across all 15 cells. It scored 1.5/5:

| Task | Score | What happened |
|------|:-----:|---------------|
| fs_current_directory | 0.0 | Emitted bash JSON but scorer didn't detect benchmark tool intent |
| fs_list_project | 0.25 | Called `bash` with `ls -la` — recognized as tool attempt but wrong tool |
| fs_read_fixture | **1.0** | **Called `read` with correct path — scored as `read_file` via alias** |
| weather_berlin_current | 0.25 | Called `bash` with `curl` — recognized as tool attempt but wrong tool |
| multi_step_read_then_weather | 0.0 | Emitted multi-line bash script, no structured tool calls |

The `read_file` PASS is genuine: the model emitted `{"name": "read", "arguments": {"path": "<PROJECT_ROOT>/misc/fixture_note.md"}}`, and the benchmark's `TOOL_ALIASES` map includes `read → read_file`. The model used Pi's `read` tool, which happens to be the same operation as the benchmark's `read_file` tool, and the scorer's alias map recognized it.

This is the only case where a platform's native tool name overlaps with a benchmark tool name. Pi's `read` tool and the benchmark's `read_file` tool both read a file by path — same semantics, different name. The alias map bridges them. No other platform has a tool that aliases to `get_cwd`, `list_directory`, or `get_weather`.

**Real-world implication:** Pi's native tool-calling layer works — the model can call bash, read, write, edit. But the benchmark tools (`get_cwd`, `list_directory`, `read_file`, `get_weather`) don't exist in Pi's tool registry. The model follows Pi's tool format, not the benchmark's. The one partial pass (qwen2.5-coder:7b's `read` → `read_file`) shows that when a platform tool happens to have the same semantics as a benchmark tool, the model can use it correctly — but this is coincidental, not by design.

## The Tool Registration Gap

All three native adapters share the same root issue: **the benchmark's tools are not registered with the platform.**

| Platform | Has `get_cwd`? | Has `list_directory`? | Has `read_file`? | Has `get_weather`? |
|----------|:-:|:-:|:-:|:-:|
| OpenClaw | No (has `read`, `exec`) | No (has `read`) | Yes (has `read`, aliased) | No |
| Hermes | No (has `bash`) | No (has `bash`) | No (has `read`) | No |
| Pi | No (has `bash`) | No (has `bash`) | Yes (has `read`, aliased) | No |

No platform has `get_weather` — that's a benchmark-owned tool that calls the Open-Meteo API. No platform has `get_cwd` — they all have more general filesystem or shell tools.

This means the native adapters can only test whether the model *attempts* a tool call in a recognizable format. They can't test whether the model *selects the right tool* because the right tool doesn't exist in the platform's registry — except when a platform tool name happens to alias to a benchmark tool name (Pi's `read` → benchmark's `read_file`).

## Failure Mode Summary by Model

| Model | openclaw-native | hermes-native | pi-native strict | pi-native judge | Pattern |
|-------|:-:|:-:|:-:|:-:|---------|
| mistral:7b | Context overflow | Silent session failure | 0/5 | 1/5 | Blocked by 32K context in 2/3 platforms; one Pi weather success |
| lfm2.5:latest | Model override rejected | Tool mismatch | 0/5 | 1.5/5 | Blocked by OpenClaw policy; can complete some Pi tasks |
| qwen3.5:9b | Model override rejected | Tool mismatch (only vision_analyze) | 0/5 | **3/5** | Best Pi-native task completion, despite strict 0/5 |
| qwen2.5-coder:7b | Context overflow | Silent session failure | **1.5/5** | 0/5 | Emits parseable JSON, but did not produce completed Pi answers |
| ornith:9b | Model override rejected | Tool mismatch (only vision_analyze) | 0/5 | **2/5** | Completes some Pi tasks via platform tools |

The pattern is clear: **32K-context models** (mistral:7b, qwen2.5-coder:7b) are blocked by context limits in OpenClaw and Hermes but can run through Pi. **40K+ context models** (qwen3.5:9b, ornith:9b, lfm2.5) are blocked by OpenClaw's model-override policy and Hermes's toolset configuration, but run through Pi with tool mismatch.

## Do ReAct Rankings Predict Native Performance?

**No.** The ReAct rankings from article-2 show:

1. qwen2.5-coder:7b — 5/5 smoke, perfect speed
2. qwen3.5:9b — 4/5 agentic, strongest reasoning
3. ornith:9b — best grounding, reliable

Through strict native scoring, all three score 0/5 except qwen2.5-coder:7b's 1.5/5 on pi-native. Through LLM-judged task completion, the picture changes: qwen3.5:9b scores 3/5 on Pi, Ornith:9b scores 2/5, and qwen2.5-coder:7b drops to 0/5.

So the answer depends on which native question you ask:

- **Protocol compatibility:** qwen2.5-coder:7b transfers best. It emits parseable JSON tool calls, even when Pi has not executed them into final answers.
- **User-visible task completion:** qwen3.5:9b and Ornith:9b transfer better through Pi. They use platform tools or platform-derived context to answer real tasks, even when strict JSON parsing misses that.

The ReAct rankings still do not predict OpenClaw-native or Hermes-native performance, because those runs are dominated by platform configuration failures. But they do partially predict Pi-native task quality: the stronger ReAct models are the ones that can turn Pi's general tools into useful answers.

## Two Layers of Native Testing

The results confirm that "native tool calling" is actually two separate things:

1. **Format compliance** — Can the model emit a structured tool call (JSON, function call) instead of free text? This is what the `infer model run` path with `NATIVE_SYSTEM_PROMPT` tests. It's equivalent to ReAct but with JSON instead of Action/Action Input.

2. **Platform integration** — Does the model work with the platform's real tool registry, real tool schemas, and real tool execution? This is what `openclaw agent`, `hermes chat`, and `pi --print` (with tools) test.

The ReAct adapters already test layer 1 (format compliance) through the benchmark's own prompt and parser. The native adapters attempt to test layer 2 (platform integration) but fail because the benchmark's tools aren't registered with the platforms — with the single exception of Pi's `read` tool aliasing to the benchmark's `read_file`.

## What Would Fix This

To properly test platform integration, the native adapters would need to:

**Option A: Register benchmark tools with each platform.** Create OpenClaw tools, Hermes tools, and Pi extensions that wrap the benchmark's `get_cwd`, `list_directory`, `read_file`, and `get_weather` functions. Then the model would see the benchmark tools in the platform's native format and could call them through the platform's tool-calling layer. This is the most faithful test but requires platform-specific integration work.

**Option B: Use the platform's own tools and adapt the tasks.** Instead of testing whether the model calls `list_directory`, test whether it calls `bash ls` (Pi) or `read` (OpenClaw/Hermes). Map the benchmark tasks to platform-equivalent tools. This tests real platform integration but makes cross-runtime comparison harder — you're comparing different tool ecosystems.

**Option C: Accept the current findings as real platform constraints.** The context overflow (OpenClaw), model-override rejection (OpenClaw), silent session failure (Hermes), toolset misconfiguration (Hermes), and tool mismatch (Pi) are all real findings that would affect anyone trying to use these platforms with these models. Document them and move on.

## The OpenClaw Context Isolation Finding

OpenClaw's `infer model run` path (used by openclaw-react) works perfectly with 7B models because it's stateless — no workspace context. But `openclaw agent` loads everything: AGENTS.md, MEMORY.md, skills, tool schemas.

This is by design — OpenClaw agent mode is meant to be a full agent with access to its workspace, memory, and tools. But it means agent mode has a de facto minimum context requirement of ~56K tokens, which excludes most 7B models with default Ollama settings (32K).

Additionally, OpenClaw's model-override security policy means that even models with sufficient context (qwen3.5:9b at 40K, lfm2.5 at 256K) cannot be tested through `openclaw agent --model ...` without first allowing the override in the agent configuration. This is a security feature, not a bug — but it's a barrier for benchmarking.

The fix for production use is straightforward: either use a model with 65K+ context (e.g., qwen3.5:9b with `num_ctx 65536`) and allow the model override in OpenClaw config, or use the `infer` path for lightweight tasks. For the benchmark, the finding is that **OpenClaw agent mode and small models are incompatible without configuration changes — both context and model-override policy must be adjusted**.

## The Hermes Context and Toolset Findings

Hermes is unique among the three platforms in that older versions (v0.17.0) actively refused to run a model with insufficient context, producing a clear error message. The newer version (v0.18.2) no longer emits this message — it creates a session but produces no model output, which is harder to diagnose.

For models with sufficient context (qwen3.5:9b, ornith:9b, lfm2.5), Hermes runs but only exposes `vision_analyze` to the model — not the `safe` toolset (`bash`, `read`, `write`, `edit`) that the benchmark requested via `--toolsets safe`. The models explicitly note that only `vision_analyze` is available. This suggests a toolset registration issue in Hermes v0.18.2.

For the benchmark, the findings are:
1. **Hermes has a hard 64K context floor** for tool-using models. Models with 32K context produce empty sessions silently (v0.18.2) or get an explicit rejection (v0.17.0).
2. **Hermes v0.18.2 may not correctly register the `safe` toolset** — models report only `vision_analyze` as available.
3. **Even with correct toolset registration, the benchmark tools would not be available** — Hermes's tools (`bash`, `read`, `write`, `edit`) are not the benchmark's tools.

## The Pi Tool Layer Finding

Pi is the most context-efficient of the three platforms. With `--no-context-files --no-skills --no-extensions --offline`, the system prompt is minimal — no workspace files, no skills, no extensions. The model has plenty of context room.

Pi's native tools (bash, read, write, edit) are general-purpose, not benchmark-specific. The model correctly identifies that it needs to list files or read a file, and it attempts to use Pi's tools to do so — but the benchmark scorer doesn't recognize Pi's tool-call format as a benchmark tool call, unless the tool name happens to alias (Pi's `read` → benchmark's `read_file`).

The strict qwen2.5-coder:7b partial pass and the LLM-judged qwen3.5/Ornith wins show two different Pi-native skills:

1. **Tool-call syntax skill**: qwen2.5-coder emits clean JSON that a parser can recognize. That matters for integration work, but it is not the same as completing the task.
2. **Task-completion skill**: qwen3.5:9b and Ornith:9b produce useful final answers through Pi's tool environment. The manual Ornith session made this obvious: when asked for Paris weather, Ornith first declined, then used `bash` with `curl wttr.in/Paris` when prompted, and returned current weather.

This means Pi-native should be evaluated with two metrics. The strict score catches protocol interoperability. The judge score catches whether the user got a useful result.

## Conclusion

The native adapter results are not a failure of the benchmark or the adapters. They are **real findings about platform compatibility with small models**:

1. **OpenClaw agent mode** requires ~56K tokens of workspace context, overflowing 32K-context models. Additionally, the model-override security policy blocks testing of 40K+ context models without configuration changes. Use `infer` for lightweight tasks or increase `num_ctx` and allow model overrides.

2. **Hermes** has a hard 64K context minimum for tool-using models. Models with 32K context produce empty sessions silently in v0.18.2. Models with sufficient context still fail because the benchmark tools aren't registered — and Hermes v0.18.2 may not correctly register even its own safe toolset.

3. **Pi** has the best context isolation and actually lets models complete tasks. Strict benchmark-tool scoring misses most of that, because Pi's tools (bash, read, write, edit) don't include benchmark-specific tools. LLM-judged scoring gives Pi-native qwen3.5:9b 3/5 and Ornith:9b 2/5.

4. **No platform registers the benchmark's tools** (`get_cwd`, `list_directory`, `read_file`, `get_weather`). To properly test platform-native tool calling, the benchmark tools would need to be registered as platform extensions.

5. **ReAct rankings do not predict strict native performance, but they partly predict Pi task completion.** qwen3.5:9b and Ornith:9b are useful through Pi when judged flexibly. qwen2.5-coder:7b is best at parseable tool-call syntax but did not produce completed Pi answers in this run.

6. **Native scoring needs both strict and flexible layers.** Strict parsing diagnoses tool-registration and protocol compatibility. LLM-as-judge scoring diagnoses whether the platform response actually helped the user.

These findings are the value of the native adapters. They do not produce a single simple score; they produce a diagnosis. And the diagnosis is clear: **OpenClaw and Hermes are blocked by platform configuration for these local models, Pi is the only native path that currently completes tasks, and strict benchmark-tool parsing undercounts real Pi usefulness.**

The next step is either registering benchmark tools as platform extensions (Option A) or accepting these as real platform constraints and focusing the benchmark on the ReAct adapters, which already provide fair cross-runtime comparison (article-2).

---

*All benchmark data, result files, and the harness itself are open source at [github.com/ebelo/local-agent-bench](https://github.com/ebelo/local-agent-bench). Native adapter runs were conducted on Lenovo P14s Gen 6, NVIDIA RTX PRO 1000 Blackwell 8GB, WSL2 Ubuntu 24.04, Ollama 0.30.10. OpenClaw 2026.6.8, Hermes v0.18.2 (2026.7.7.2), Pi 0.79.8. All runs sequential, smoke benchmark (5 tasks), 2026-07-08. 15 cells: 5 models × 3 native adapters.*

*Generated by OpenClaw 2026.6.8 · model=ollama/glm-5.2:cloud · reasoning=off*
