# Local Agent Bench Comparison: lfm2.5 vs qwen3.5:9b

**Date:** 2026-06-10
**Benchmark:** smoke (5 tasks)
**Runtime:** raw-ollama-react
**Hardware:** NVIDIA RTX PRO 1000 Blackwell, 8GB VRAM, WSL2
**Ollama:** 0.30.7

---

## Models Compared

| Property | lfm2.5:latest | qwen3.5:9b |
|----------|---------------|------------|
| Parameter size | 8.5B | ~9B |
| Architecture | lfm2moe (MoE, 32 experts, 4 active) | Dense |
| Quantization | Q4_K_M | Q4_K_M (inferred) |
| Model size on disk | 5.2 GB | 6.6 GB |
| Context length | 128,000 | Unknown (likely 32K-128K) |

---

## Benchmark Results

| Task | Category | lfm2.5:latest | qwen3.5:9b |
|------|----------|---------------|------------|
| fs_current_directory | filesystem | **0.25** — INVALID_TOOL_SYNTAX | **1.0** — PASS |
| fs_list_project | filesystem | **0.25** — INVALID_TOOL_SYNTAX | **0.25** — WRONG_TOOL |
| fs_read_fixture | filesystem | **0.25** — INVALID_TOOL_SYNTAX | **0.25** — WRONG_TOOL |
| weather_berlin_current | weather | **0.75** — IGNORED_TOOL_RESULT | **1.0** — PASS |
| multi_step_read_then_weather | multi_step | **0.25** — INVALID_TOOL_SYNTAX | **0.75** — IGNORED_TOOL_RESULT |

**Pass rate:** lfm2.5 = 0/5 | qwen3.5:9b = 2/5

---

## Latency per Task

| Task | lfm2.5 (ms) | qwen3.5:9b (ms) | Speedup |
|------|-------------|-----------------|---------|
| fs_current_directory | 3,614 | 67,386 | 18.6× |
| fs_list_project | 2,848 | 104,926 | 36.8× |
| fs_read_fixture | 1,954 | 128,336 | 65.7× |
| weather_berlin_current | 8,141 | 129,838 | 15.9× |
| multi_step_read_then_weather | 4,256 | 120,423 | 28.3× |

**Average speedup:** lfm2.5 is ~33× faster per task on this hardware.

---

## Key Findings

### ReAct Format Compliance
- **qwen3.5:9b** correctly emits `Thought → Action → Action Input → JSON` format on most tasks
- **lfm2.5** frequently violates the required format:
  - Omits `Action Input: {}` for zero-argument tools (e.g., `get_cwd`)
  - Outputs `Action: {"path": "."}` instead of `Action: tool_name` + `Action Input: {...}`
  - Returns empty assistant content on 2/5 tasks (fs_read_fixture, multi_step)

### Tool Selection
- **qwen3.5:9b** calls valid tools but occasionally selects the wrong one (e.g., `get_cwd` instead of `list_directory` for "list files")
- **lfm2.5** when it does emit valid tool calls, selects correct tools (e.g., `get_weather` for weather task)

### Tool Result Utilization
- **qwen3.5:9b** passes weather task fully (1.0) — reads temperature from tool result and includes it in final answer
- **lfm2.5** calls `get_weather` successfully but outputs thinking markup (`

The user asks...`) instead of incorporating the tool result into a final answer — scored 0.75 (IGNORED_TOOL_RESULT)
- Both models struggle with multi-step tasks where tool result must be fed back into a second tool call

### Empty / Failed Responses
- **lfm2.5** returns completely empty content on `fs_read_fixture` and `multi_step_read_then_weather`
- **qwen3.5:9b** always returns non-empty content

---

## Failure Layer Breakdown

### lfm2.5:latest
| Failure Reason | Count | Layer |
|----------------|-------|-------|
| INVALID_TOOL_SYNTAX | 4 | Tool protocol |
| IGNORED_TOOL_RESULT | 1 | Agent loop |

### qwen3.5:9b
| Failure Reason | Count | Layer |
|----------------|-------|-------|
| WRONG_TOOL | 2 | Tool selection |
| IGNORED_TOOL_RESULT | 1 | Agent loop |
| PASS | 2 | — |

---

## Verdict

**qwen3.5:9b** is the more capable agent model for ReAct-style tool use. It understands the protocol, emits valid tool calls, and can utilize tool results. Its main weaknesses are wrong-tool selection on ambiguous tasks and incomplete multi-step reasoning.

**lfm2.5** is dramatically faster (~33×) but fails at basic ReAct format compliance. It appears to understand tool semantics (selects correct tools when format is roughly correct) but cannot reliably follow the strict `Action: name` + `Action Input: {...}` envelope required by this benchmark. Empty responses on longer prompts suggest potential context or prompt-format sensitivity issues.

**Recommendation:** lfm2.5 may work better with a different prompting strategy (e.g., native function calling, XML tags, or simpler tool descriptions) rather than the explicit ReAct format used here.

---

## Raw Result Files

- lfm2.5: `results/lfm2.5_smoke_20260610_220301.json`
- qwen3.5:9b: `results/qwen3.5_9b_smoke_manual.json` (manually collected due to timeout)

---

## Notes

- Benchmark timeout (`OLLAMA_TIMEOUT`) was increased from 60s to 300-600s for qwen3.5:9b runs due to slow per-token generation on this GPU
- Both models were tested sequentially (not concurrently) to avoid GPU memory contention
- The ReAct loop was limited to `--max-steps 2` for qwen3.5:9b initial attempts; final manual run used `--max-steps 3`
