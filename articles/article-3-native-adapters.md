# Native Adapters and Platform-Native Use Cases

*Two native topics, three runtimes, six models: strict tool compatibility still mostly fails, while platform-native use cases show where each runtime actually becomes useful.*

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

Native testing now has two sequential topics.

### Topic 1: Strict Benchmark-Tool Compatibility

All three native adapters first run the benchmark's smoke tasks (5 tasks: get_cwd, list_directory, read_file, get_weather, multi-step). This scoring layer checks whether the model emitted structured tool-call JSON matching the benchmark's tool definitions (`get_cwd`, `list_directory`, `read_file`, `get_weather`).

### Topic 2: Platform-Native Use Cases

The second suite, `benchmarks/platform_native.json`, asks use-case tasks and lets the runtime choose its own tools. The tasks are: current directory, list project files, read fixture codename, current Berlin weather, and recover from a missing path. Each prompt asks the agent to include a short evidence line naming the command/tool used and the relevant output.

Use-case completion is scored by an LLM judge (`ollama/glm-5.2:cloud` through OpenClaw `infer`) with deterministic text assertions as guardrails. This was added after a manual Pi session with Ornith:9b showed the problem clearly: when nudged to use `bash`, Ornith fetched live weather from `wttr.in` and answered correctly, but strict scoring still gave 0/5 because it did not emit benchmark-specific `get_weather` JSON.

After Ornith passed all five platform-native use cases through Pi, a harder follow-up suite, `benchmarks/platform_native_ladder.json`, was added to probe levels 6-8: live web/API grounding, local HTML/Markdown navigation, and end-to-end project-health or release-readiness work.

## The Six Models

| Model | Family | Size | Ollama Context | ReAct ranking |
|-------|--------|------|:-:|--------|
| qwen2.5-coder:7b | Qwen2.5 | 7.6B | 32K | #1 overall (5/5 smoke, perfect speed) |
| qwen3.5:9b | Qwen3.5 | 9.7B | 262K | #2 (4/5 agentic, strongest reasoning) |
| Ornith:9b | Qwen3.5 (Ornith-1.0) | 9.0B | 262K | #3 (best grounding, reliable) |
| mistral:7b | Mistral | 7.2B | 32K | #4 (protocol-compliant, fast on raw) |
| lfm2.5:latest | LFM2 MoE | 8.5B | 128K | #5 (fast but prompt-format sensitive) |
| ibm/granite4.1:8b | Granite | 8.8B | 131K | #6 (fast but low capability) |

These are the six models that produced the ReAct rankings in article-2. Testing them natively answers: *do the ReAct rankings predict platform-native performance?*

## Strict Results: Post-Config OpenClaw Still Scores 0/5

| Adapter | Model | Strict Score | Root Cause | Avg Latency |
|---------|-------|:------------:|------------|:-----------:|
| openclaw-native | mistral:7b | 0/5 | Context overflow (full OpenClaw workspace vs 32K window) | 5.1s |
| openclaw-native | qwen2.5-coder:7b | 0/5 | Context overflow (full OpenClaw workspace vs 32K window) | 5.1s |
| openclaw-native | qwen3.5:9b | 0/5 | Config fixed; one direct answer, four 180s timeouts | 165.9s |
| openclaw-native | ornith:9b | 0/5 | Config fixed; five 180s timeouts | 180.1s |
| openclaw-native | lfm2.5:latest | 0/5 | Config fixed; four 180s timeouts, one unsupported no-tool answer | 154.6s |
| openclaw-native | ibm/granite4.1:8b | 0/5 | Config fixed; five 180s timeouts | 180.1s |
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

After fixing OpenClaw's local model configuration, qwen3.5, Ornith, LFM2.5, and Granite are no longer rejected by the model-override policy. They are now configured, available, and above the context minimum. The post-config result is still 0/5 on strict smoke, but for a different reason: full OpenClaw-native agent turns are too slow or do not emit benchmark-compatible tool calls under the loaded workspace/tool context.

The one non-zero strict native result remains qwen2.5-coder:7b through pi-native. It scored 1.5/5: a perfect `read_file` call (1.0), a `bash` call instead of `list_directory` (0.25), and a `bash` call instead of `get_weather` (0.25).

That strict result is useful, but incomplete. It measures benchmark-tool protocol compatibility, not whether the platform session actually helped the user.

## Platform-Native Use-Case Results

The platform-native suite evaluates a more practical question: did the runtime/model combination complete the use case using its own tools? This is where Pi separates from the other two native runtimes.

| Adapter | mistral:7b | lfm2.5 | qwen3.5:9b | qwen2.5-coder:7b | ornith:9b | Interpretation |
|---------|:---------:|:------:|:----------:|:----------------:|:--------:|----------------|
| openclaw-native | 0/5 | 1/5 | 0/5 | 0/5 | 0/5 | Config fixed; mostly blocked by full-agent timeout/latency |
| hermes-native | 0/5 | 0/5 | 0/5 | 0/5 | 0.5/5 | Mostly blocked by silent sessions or unavailable tools |
| pi-native | 1/5 | 3/5 | 3/5 | 1/5 | **5/5** | Pi can complete real tasks when prompted for evidence |

The important correction: **Ornith:9b through Pi is not a real 0/5 user experience.** In the platform-native suite it passed all five use cases: current directory, project listing, fixture read, current weather, and missing-path recovery. Strict scoring missed this because the work was done through Pi-native `bash`/`read` style behavior rather than benchmark `list_directory`/`get_weather` JSON.

qwen3.5:9b and lfm2.5 both scored 3/5 through Pi. qwen2.5-coder:7b and mistral:7b scored 1/5. Hermes produced only one partial result: Ornith got 0.5/5 for identifying the current directory from context, but it still lacked usable file/weather tools. OpenClaw-native improved from a configuration standpoint, but not from a benchmark standpoint: after adding the models to OpenClaw config, only LFM2.5 got a non-zero platform-native result, passing the weather use case while most other tasks timed out.

### Per-Task Pi Results

| Model | cwd | list project | read fixture | weather | recovery | Total |
|-------|:---:|:------------:|:------------:|:-------:|:--------:|:-----:|
| mistral:7b | 1 | 0 | 0 | 0 | 0 | 1/5 |
| lfm2.5 | 1 | 1 | 0 | 0 | 1 | 3/5 |
| qwen3.5:9b | 1 | 1 | 0 | 0 | 1 | 3/5 |
| qwen2.5-coder:7b | 1 | 0 | 0 | 0 | 0 | 1/5 |
| Ornith:9b | 1 | 1 | 1 | 1 | 1 | **5/5** |

There is an important caveat: Pi's `--print` output is not a structured tool trace. The prompt asks for evidence, and the judge evaluates the answer plus evidence line. That is much better than scoring final text alone, but it is still weaker than a runtime transcript that records every tool call and output. Platform-native use-case results should therefore be read as **holistic user-experience evidence**, not as a formal proof of tool execution.

### Ornith Limit Probe: Platform-Native Ladder

Because Ornith:9b passed all five basic Pi-native use cases, the next question was: *where does it break?* The follow-up suite `benchmarks/platform_native_ladder.json` adds seven harder tasks:

| Level | Task Type | Tasks |
|------:|-----------|-------|
| 6 | Web/API grounding | GitHub repo metadata, Berlin-vs-Zurich weather comparison, remote README cross-check |
| 7 | Navigation | Follow local HTML links, follow local Markdown links |
| 8 | End-to-end work | Release-readiness brief, project-health check with local tests |

The first one-shot run scored **2/7**, but Emman observed the same model in Pi sometimes drifts into long reasoning and can hit a maximum-output cutoff. The ladder was therefore repeated as five fully independent Pi-native subprocess runs. The repeated totals were:

```text
[0.0, 2.5, 1.0, 1.35, 2.0]
mean = 1.37/7
stdev = 0.96
range = 0.0-2.5
```

No captured repeat contained the explicit "maximum output token limit" string, but the variance was large enough to make the point: **single native runs are not statistically trustworthy.**

| Task | Level | Result | What Happened |
|------|:----:|:------:|---------------|
| GitHub repo metadata | 6 | 1/5 passes | Sometimes correct, often rejected for weak execution evidence |
| Weather comparison | 6 | 1/5 passes | One live-weather pass; other runs hallucinated or lacked evidence |
| Remote README cross-check | 6 | 0/5 passes | Consistent failure, often unrelated task drift |
| HTML link navigation | 7 | 0/5 passes | Correct-looking `violet-harbor` answers, but no convincing tool trace |
| Markdown link navigation | 7 | 0/5 passes, one partial | Correct-looking `delta-17` answers, but usually weak evidence |
| Release-readiness brief | 8 | 1/5 passes, two partials | Sometimes synthesizes well, often weak weather/source evidence |
| Project-health check | 8 | 2/5 passes | Best higher-level task; passes when `pytest` output is concrete |

This is the first real ceiling: **Ornith can complete straightforward native tasks, but levels 6-8 expose evidence reliability, task-drift, and run-to-run variance.** It often knows the right answer shape and sometimes the right answer, but without structured Pi tool traces the judge cannot always distinguish real execution from plausible reconstruction. The strongest higher-level signal was the project-health task, where command output (`44 passed` or `45 passed`, depending on the code state) and file evidence were concrete.

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

### 1b: Config Fixed, Full-Agent Timeout Remains (lfm2.5, qwen3.5:9b, ornith:9b, Granite)

**What happened:** The first native matrix found a configuration problem: lfm2.5:latest, qwen3.5:9b, and ornith:9b were not allowed as `--model` overrides for agent `main`:

> `Error: Model override "ollama/qwen3.5:9b" is not allowed for agent "main".`

That was a **configuration gate**, not a context issue. OpenClaw's agent configuration restricts which models can be used for a given agent. After adding qwen3.5, Ornith, LFM2.5, and Granite to `agents.defaults.models` and the Ollama provider catalog in `/home/ebelo/.openclaw/openclaw.json`, OpenClaw reported all four as configured and available.

Fresh one-turn checks then succeeded: Ornith returned `OK` in about 30 seconds and qwen3.5 returned `OK` in about 106 seconds, both with `contextTokens: 262144`.

The post-config benchmark still failed. qwen3.5, Ornith, Granite, and most LFM2.5 tasks timed out at 180 seconds per task under full OpenClaw-native agent mode. LFM2.5 produced the only non-zero OpenClaw-native use-case result: 1/5 on the Berlin weather task.

**Real-world implication:** OpenClaw's agent mode has a de facto minimum context requirement and a high prompt/tool-schema cost. Fixing model allowlisting is necessary, but not sufficient. On this local 8GB VRAM setup, full OpenClaw-native agent mode remains too heavy for these small local models unless the injected workspace/tool context is reduced.

**Potential OpenClaw improvement:** Add a `--no-context-files` or `--bare` flag to `openclaw agent` that skips loading AGENTS.md, MEMORY.md, skills, and tool schemas — similar to Pi's `--no-context-files --no-skills` flags. This would allow agent mode to work with small models for lightweight tasks. Also keep the model allowlist explicit and documented so benchmark or local-model agents can be configured without ambiguity.

## Finding 2: Hermes Has Two Failure Modes for 32K Models

### 2a: Silent Session Failure (mistral:7b, qwen2.5-coder:7b)

**What happened:** `hermes chat --query --quiet --model ollama/mistral:7b` creates a session but produces no model output. The only response is a session ID:

> `session_id: 20260708_202233_5f7e45`

No error message, no model reasoning, no tool calls. Hermes v0.18.2 appears to accept the request but the model never generates. This is likely because both models have 32K default context and Hermes's tool-calling infrastructure requires more — but unlike the older Hermes v0.17.0 (which produced an explicit "64,000 tokens required" error), the new version silently produces an empty session.

**The earlier explicit rejection:** During initial testing with Hermes v0.17.0, mistral:7b produced a hard error:

> "Ollama loaded `mistral:7b` with only 32,768 tokens of runtime context, but Hermes needs at least 64,000 tokens for reliable tool use. Increase the Ollama context for this model and restart/reload the model before trying again."

Hermes v0.18.2 no longer emits this message. The 64K requirement still exists but the error is silent — the session is created, no output is produced, and the adapter sees only the session ID.

### 2b: Tool Mismatch (lfm2.5:latest, qwen3.5:9b, ornith:9b)

**What happened:** These three models have enough context to run through Hermes (local Ollama reports LFM2.5 at 128K and qwen3.5/Ornith at 262K). Hermes runs and the model responds — but it can't find the benchmark tools.

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
| lfm2.5:latest | 0/5 strict; 1/5 use-case, mostly timeouts | Tool mismatch | 0/5 | 3/5 | OpenClaw config fixed but too slow; can complete some Pi tasks |
| qwen3.5:9b | Config fixed, but mostly 180s timeouts | Tool mismatch (only vision_analyze) | 0/5 | **3/5** | Strong Pi-native task completion, despite strict 0/5 |
| qwen2.5-coder:7b | Context overflow | Silent session failure | **1.5/5** | 1/5 | Emits parseable JSON, but mostly did not produce completed Pi answers |
| ornith:9b | Config fixed, but five 180s timeouts | Tool mismatch (only vision_analyze) | 0/5 | **5/5** | Best platform-native result through Pi |
| ibm/granite4.1:8b | Config fixed, but five 180s timeouts | Not tested in first native matrix | — | — | Long context is not enough if native full-agent turns stall |

The pattern is clear: **32K-context models** (mistral:7b, qwen2.5-coder:7b) are blocked by context limits in OpenClaw and Hermes but can run through Pi. **Long-context local models** (qwen3.5:9b, ornith:9b, lfm2.5, Granite) now pass OpenClaw's model-configuration gate, but the full native agent turn is too slow for this benchmark on the local 8GB GPU setup. In Hermes, the same long-context models still hit toolset mismatch. In Pi, the benchmark tools are absent but the native tool ecosystem is usable enough for task completion.

## Do ReAct Rankings Predict Native Performance?

**No.** The ReAct rankings from article-2 show:

1. qwen2.5-coder:7b — 5/5 smoke, perfect speed
2. qwen3.5:9b — 4/5 agentic, strongest reasoning
3. ornith:9b — best grounding, reliable

Through strict native scoring, all three score 0/5 except qwen2.5-coder:7b's 1.5/5 on pi-native. Through platform-native use-case scoring, the picture changes: Ornith:9b scores 5/5 on Pi, qwen3.5:9b scores 3/5, and qwen2.5-coder:7b drops to 1/5.

So the answer depends on which native question you ask:

- **Protocol compatibility:** qwen2.5-coder:7b transfers best. It emits parseable JSON tool calls, even when Pi has not executed them into final answers.
- **User-visible task completion:** Ornith:9b transfers best through Pi. qwen3.5:9b and lfm2.5 are useful but incomplete. qwen2.5-coder's ReAct strength does not translate to platform-native completion in this run.

The ReAct rankings still do not predict OpenClaw-native or Hermes-native performance, because those runs are dominated by platform/runtime integration costs rather than pure model capability. OpenClaw-native moved from "configuration rejected" to "configured but too slow"; Hermes remains dominated by toolset exposure; Pi-native is the only layer where user-visible task completion separates models.

## Two Layers of Native Testing

The results confirm that "native tool calling" is actually two separate things:

1. **Format compliance** — Can the model emit a structured tool call (JSON, function call) instead of free text? This is what the `infer model run` path with `NATIVE_SYSTEM_PROMPT` tests. It's equivalent to ReAct but with JSON instead of Action/Action Input.

2. **Platform integration** — Does the model work with the platform's real tool registry, real tool schemas, and real tool execution? This is what `openclaw agent`, `hermes chat`, and `pi --print` (with tools) test.

The ReAct adapters already test layer 1 (format compliance) through the benchmark's own prompt and parser. The native adapters attempt to test layer 2 (platform integration) but fail because the benchmark's tools aren't registered with the platforms — with the single exception of Pi's `read` tool aliasing to the benchmark's `read_file`.

## What Would Fix This

To properly test platform integration, the native adapters would need to:

**Option A: Register benchmark tools with each platform.** Create OpenClaw tools, Hermes tools, and Pi extensions that wrap the benchmark's `get_cwd`, `list_directory`, `read_file`, and `get_weather` functions. Then the model would see the benchmark tools in the platform's native format and could call them through the platform's tool-calling layer. This is the most faithful test but requires platform-specific integration work.

**Option B: Use platform-native use cases.** Instead of testing whether the model calls `list_directory`, ask it to list the project and let it choose `bash`, `read`, or any other platform tool. This is now implemented as `benchmarks/platform_native.json`. It tests real platform usefulness but makes cross-runtime comparison less controlled — you're comparing different tool ecosystems and relying on evidence plus LLM judging.

**Option C: Register benchmark tools with each platform later.** The context overflow (OpenClaw), full-agent timeout/latency (OpenClaw), silent session failure (Hermes), toolset misconfiguration (Hermes), and tool mismatch (Pi) are all real findings. A future stricter native suite could still register identical benchmark tools as platform extensions once each platform exposes a clean extension path.

## The OpenClaw Context Isolation Finding

OpenClaw's `infer model run` path (used by openclaw-react) works perfectly with 7B models because it's stateless — no workspace context. But `openclaw agent` loads everything: AGENTS.md, MEMORY.md, skills, tool schemas.

This is by design — OpenClaw agent mode is meant to be a full agent with access to its workspace, memory, and tools. But it means agent mode has a de facto minimum context requirement of ~56K tokens, which excludes most 7B models with default Ollama settings (32K).

The initial native matrix also exposed an OpenClaw configuration issue: qwen3.5:9b, Ornith:9b, LFM2.5, and Granite were not present in the agent's configured Ollama model catalog. After adding them to `/home/ebelo/.openclaw/openclaw.json`, fresh one-turn native checks succeeded: Ornith returned `OK` in about 30 seconds, and qwen3.5 returned `OK` in about 106 seconds, both with `contextTokens: 262144`.

But the post-config benchmark still failed: strict smoke remained 0/5 for every OpenClaw-native model, and platform-native use cases were 0/5 except LFM2.5 at 1/5 on weather. The finding is therefore sharper now: **OpenClaw-native can be configured to accept these local long-context models, but full agent mode is still too heavy and slow for this local 8GB GPU benchmark path.** Use `infer` for lightweight local tasks, or reduce injected workspace/tool context before expecting small local models to behave like practical full OpenClaw agents.

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

The strict qwen2.5-coder:7b partial pass and the platform-native Ornith/qwen3.5/lfm2.5 results show two different Pi-native skills:

1. **Tool-call syntax skill**: qwen2.5-coder emits clean JSON that a parser can recognize. That matters for integration work, but it is not the same as completing the task.
2. **Task-completion skill**: Ornith:9b, qwen3.5:9b, and lfm2.5 produce useful final answers through Pi's tool environment. The manual Ornith session made this obvious: when asked for Paris weather, Ornith first declined, then used `bash` with `curl wttr.in/Paris` when prompted, and returned current weather.

This means Pi-native should be evaluated with two metrics. The strict score catches protocol interoperability. The judge score catches whether the user got a useful result.

## Conclusion

The native adapter results are not a failure of the benchmark or the adapters. They are **real findings about platform compatibility with small models**:

1. **OpenClaw agent mode** requires a large injected workspace/tool context, overflowing 32K-context models. After adding qwen3.5, Ornith, LFM2.5, and Granite to the OpenClaw model config, model override is no longer the blocker; native full-agent turns are now dominated by 180s timeouts and high latency. Use `infer` for lightweight tasks or reduce agent context before expecting local 8GB-GPU models to run full OpenClaw agent workflows.

2. **Hermes** has a hard 64K context minimum for tool-using models. Models with 32K context produce empty sessions silently in v0.18.2. Models with sufficient context still fail because the benchmark tools aren't registered — and Hermes v0.18.2 may not correctly register even its own safe toolset.

3. **Pi** has the best context isolation and actually lets models complete tasks. Strict benchmark-tool scoring misses most of that, because Pi's tools (bash, read, write, edit) don't include benchmark-specific tools. Platform-native use-case scoring gives Pi-native Ornith:9b 5/5, qwen3.5:9b 3/5, and lfm2.5 3/5. A harder repeated ladder probe drops Ornith to a mean of 1.37/7, showing its current limit around levels 6-8.

4. **No platform registers the benchmark's tools** (`get_cwd`, `list_directory`, `read_file`, `get_weather`). To properly test platform-native tool calling, the benchmark tools would need to be registered as platform extensions.

5. **ReAct rankings do not predict strict native performance, and only partly predict Pi task completion.** Ornith:9b is the platform-native Pi winner even though qwen2.5-coder:7b is the controlled ReAct winner.

6. **Native scoring needs both strict and flexible layers, plus repetition.** Strict parsing diagnoses tool-registration and protocol compatibility. LLM-as-judge scoring diagnoses whether the platform response actually helped the user. Independent repeated native runs are needed because Pi/Ornith shows large run-to-run variance on harder tasks.

These findings are the value of the native adapters. They do not produce a single simple score; they produce a diagnosis. And the diagnosis is clear: **OpenClaw and Hermes are blocked by platform configuration for these local models, Pi is the only native path that currently completes tasks, and strict benchmark-tool parsing undercounts real Pi usefulness.**

The next step is to keep both topics: controlled ReAct for fair model comparison, and platform-native use cases for holistic deployability. If the platforms later expose structured tool traces, the platform-native suite can become much more rigorous.

---

*All benchmark data, result files, and the harness itself are open source at [github.com/ebelo/local-agent-bench](https://github.com/ebelo/local-agent-bench). Native adapter runs were conducted on Lenovo P14s Gen 6, NVIDIA RTX PRO 1000 Blackwell 8GB, WSL2 Ubuntu 24.04, Ollama 0.30.10. OpenClaw 2026.6.8, Hermes v0.18.2 (2026.7.7.2), Pi 0.79.8. All runs sequential, 2026-07-08 and 2026-07-09. Strict native suite: 15 cells × 5 smoke tasks. Platform-native suite: 15 cells × 5 use-case tasks. Platform-native ladder probe: Ornith:9b through Pi, 7 harder tasks, 5 independent repeats.*

*Generated by OpenClaw 2026.6.8 · model=ollama/glm-5.2:cloud · reasoning=off*
