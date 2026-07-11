# Diagnosing Local LLM Agent Tool Use Under Clean-Room Conditions

## A repeated controlled and runtime-native benchmark of six local models

**Author:** Emmanuel Belo  
**Project:** Local Agent Bench  
**Dataset:** `clean-room-2026-07`  
**Draft date:** 2026-07-09

## Abstract

Local large language models are increasingly used as agent backends, but local tool-use failures are often reported as undifferentiated model failures. This paper presents Local Agent Bench, a diagnostic benchmark for local LLM agent tool use, and reports a clean-room repeated evaluation of six 7B-9B class models served through Ollama. The study separates three layers: a primary benchmark-owned ReAct protocol through raw Ollama, a secondary controlled ReAct comparison through OpenClaw, Hermes, and Pi CLI runtimes, and a secondary platform-native diagnostic phase in which those runtimes own tool use.

The clean-room run used Docker Compose on WSL2 with an NVIDIA RTX PRO 1000 8 GB GPU, Ollama 0.31.1, and image digest `ollama/ollama@sha256:f1a705f2bd113fb8d15f85f7c217f0dc5f6bebda6b0cc42b82c3ad165ffcb9dc`. Runtime phases used a separate clean overlay with OpenClaw `2026.6.11`, Pi `0.80.3`, Hermes pinned to `f64e4f4f5768c18a53f44890747653bafcab2796`, throwaway runtime home directories, and generated provider configuration. The final aggregate loaded 397 benchmark result JSON files and 183 latency-gate result files.

In the primary controlled-core phase, a repeated 3-attempt latency/protocol gate admitted `qwen2.5-coder:7b`, `qwen3.5:9b`, and `ornith:9b`; it excluded `mistral:7b`, `lfm2.5:latest`, and `ibm/granite4.1:8b` before full runs. Across ten independent process repeats per admitted model and suite, `qwen2.5-coder:7b` achieved 5.00/5 on both smoke and agentic tasks with 3.3-3.5 seconds per task. `ornith:9b` scored 3.50/5 and 4.25/5 at 8.7 and 7.7 seconds per task. `qwen3.5:9b` scored 3.45/5 and 4.25/5 at 12.1 and 12.5 seconds per task; the nonzero smoke confidence interval was caused by one external weather API failure.

## 1. Introduction

Local LLM agents promise private, inexpensive, and controllable tool-using systems. Yet practitioners repeatedly encounter a broad complaint: a local model "cannot use tools." That phrase hides several layers of failure: malformed JSON, wrong tool choice, missing required tool use, ignored observations, runtime integration errors, context overhead, external service failures, and raw latency.

Local Agent Bench records both scores and failure reasons for each task, keeps latency visible, and separates controlled protocol testing from platform-native runtime behavior. This paper reports a clean-room repeated dataset that includes all three intended layers: primary controlled-core evidence, secondary controlled runtime-effect evidence, and secondary platform-native diagnostics.

The primary scientific claim remains scoped to the controlled-core ReAct protocol, because it is the fairest model-to-model comparison. OpenClaw, Hermes, and Pi are included as clean-room secondary evidence answering different questions: how CLI runtime scaffolding changes controlled ReAct behavior, and whether native platform use cases complete under each runtime's own tool system.

## 2. Methods

The benchmark harness is implemented in Python as `local_agent_bench`. It loads benchmark task files, builds a transcript, calls a backend adapter, parses tool calls or final answers, executes benchmark-owned tools when appropriate, records observations, and scores final results.

The primary layer is `raw-ollama-react`, which calls the Ollama HTTP API directly at `temperature=0.0` and uses the benchmark-owned ReAct prompt and parser. The secondary controlled runtime-effect layer uses `openclaw-react`, `hermes-react`, and `pi-react`: the benchmark still owns the ReAct loop, but assistant turns come from each CLI runtime. The platform-native layer uses `openclaw-native`, `hermes-native`, and `pi-native`, where the runtime owns the agent turn and tool formation.

The controlled ReAct harness exposes `get_cwd`, `list_directory`, `read_file`, and `get_weather`. The smoke suite and agentic suite each contain five tasks and are scored out of 5. Native-basic is scored out of 5; native-ladder is scored out of 7.

The primary Docker profile was `docker-compose.wsl-gpu`. Runtime phases used `docker-compose.wsl-gpu.agent-runtimes`, installing OpenClaw `2026.6.11`, Pi `0.80.3`, Hermes `f64e4f4f5768c18a53f44890747653bafcab2796`, Node.js `26.1.0`, and clean `/tmp/local-agent-bench-*` runtime homes.

Before full runs, the matrix runner applies a repeated gate per phase/runtime/model. The controlled ReAct gate warms the model, then runs `benchmarks/latency_gate.json` three times. Admission requires at least two successful attempts out of three. The controlled-core threshold is 20 seconds; runtime-effect and platform-native phases use 120 seconds. Native full runs also use a futility gate: after three completed full runs, remaining repeats are skipped if the maximum observed native total score is at or below 1.0. Gate JSON files, `latency-gate-summary.json`, and `futility-summary.json` are retained.

Every admitted phase/runtime/model/benchmark combination is run ten times as independent sequential processes. Aggregation is performed from JSON result files only.

## 3. Dataset Composition

| Phase | Jobs | Completed | Skipped | Hard failures | Elapsed |
|---|---:|---:|---:|---:|---:|
| `controlled-core` | 120 | 60 | 60 | 0 | 2554.9 s |
| `controlled-runtime-effect` | 360 | 80 | 280 | 0 | 4540.2 s |
| `platform-native-basic` | 180 | 118 | 62 | 0 | 9544.9 s |
| `platform-native-ladder` | 10 | 0 | 10 | 0 | 2117.2 s |
| `platform-native-reality` | 180 | 138 | 42 | 0 | 24333.6 s |

The final aggregate loaded 397 benchmark result JSON files and 183 latency-gate result JSON files. Execution profiles were `docker-compose.wsl-gpu` and `docker-compose.wsl-gpu.agent-runtimes`.

## 4. Primary Controlled-Core Results

Three of six models passed the repeated minimal ReAct gate.

| Model | Gate | Median latency | Passes | Failure reason |
|---|---:|---:|---:|---|
| `qwen2.5-coder:7b` | pass | 1.4 s | 3/3 | `PASS` |
| `qwen3.5:9b` | pass | 9.2 s | 3/3 | `PASS` |
| `ornith:9b` | pass | 5.0 s | 3/3 | `PASS` |
| `mistral:7b` | excluded | 1.7 s | 0/3 | score 0.00 |
| `lfm2.5:latest` | excluded | 7.6 s | 0/3 | score 0.25 |
| `ibm/granite4.1:8b` | excluded | 1.5 s | 0/3 | score 0.00 |

| Runtime | Model | Suite | Runs | Mean | 95% CI | s/task | Main failures |
|---|---|---|---:|---:|---:|---:|---|
| raw-ollama-react | `qwen2.5-coder:7b` | smoke | 10 | 5.00/5 | +/- 0.00 | 3.3 | `PASS=50` |
| raw-ollama-react | `qwen2.5-coder:7b` | agentic | 10 | 5.00/5 | +/- 0.00 | 3.5 | `PASS=50` |
| raw-ollama-react | `ornith:9b` | smoke | 10 | 3.50/5 | +/- 0.00 | 8.7 | `PASS=30`, `WRONG_TOOL=10`, `MISSING_REQUIRED_TOOL=10` |
| raw-ollama-react | `ornith:9b` | agentic | 10 | 4.25/5 | +/- 0.00 | 7.7 | `PASS=40`, `MISSING_REQUIRED_TOOL=10` |
| raw-ollama-react | `qwen3.5:9b` | smoke | 10 | 3.45/5 | +/- 0.11 | 12.1 | `PASS=29`, `WRONG_TOOL=20`, `TOOL_EXECUTION_FAILED=1` |
| raw-ollama-react | `qwen3.5:9b` | agentic | 10 | 4.25/5 | +/- 0.00 | 12.5 | `PASS=40`, `INVALID_TOOL_SYNTAX=10` |

`qwen2.5-coder:7b` is the clear controlled-core winner. It is the only model to pass all tasks across both suites, and it is also the fastest admitted model.

## 5. Secondary Runtime-Effect Results

Four of eighteen OpenClaw/Hermes/Pi controlled-runtime combinations passed the repeated admission gate and received ten full repeats per suite.

| Runtime | Model | Smoke | Agentic | s/task | Main signal |
|---|---|---:|---:|---:|---|
| openclaw-react | `ollama/mistral:7b` | 4.22/5 | 2.60/5 | 9.1-10.8 | strong smoke, weak agentic |
| hermes-react | `ollama/qwen2.5-coder:7b` | 4.20/5 | 4.28/5 | 10.2-11.2 | less reliable than raw |
| hermes-react | `ollama/mistral:7b` | 3.92/5 | 2.55/5 | 9.6-11.0 | wrapper admits model raw gate rejected |
| pi-react | `ollama/qwen2.5-coder:7b` | 4.00/5 | 4.35/5 | 4.4-5.6 | fastest secondary controlled result |

Runtime prompt scaffolding and CLI adapters materially change behavior. Mistral failed the primary raw ReAct gate but passed through OpenClaw and Hermes wrappers. Qwen2.5-Coder was perfect through raw Ollama but less reliable through Hermes and Pi wrappers.

## 6. Secondary Platform-Native Diagnostics

The native suites answer a different question from controlled ReAct: can a user-facing runtime complete practical work through its own tools and output surface? The use cases are current weather via native HTTP/curl and structured API data, filesystem/project inspection, concise synthesis from runtime-visible context, and a harder ladder task that combines live data with release-readiness reasoning. The expected behavior is not to emit raw tool traces. A passing answer cites or uses the right native evidence path, extracts the needed fields, handles units and location, and gives the user a short answer or decision.

Evaluation is judged from the observable runtime output. Deterministic checks are used for cheap latency gates and narrow guardrails; full native-basic and native-reality runs are scored by a local clean-room judge (`ollama/mistral:7b`) with explicit instructions that general web search, HTML scraping, raw JSON dumps, page placeholders, and keyword lists are failures when the task asks for structured API/native HTTP evidence. `ollama/glm-5.2:cloud` was used only as reference-behavior calibration because the clean Docker Ollama service could not authenticate to the cloud model.

| Runtime | Suite | Admitted or runs | Score range | Latency range | Signal |
|---|---:|---:|---:|---|
| openclaw-native | basic/reality | 3-run futility rows | 0.00-0.33/3 reality | 17.7-33.2 s/task | not usable in this clean native setup |
| hermes-native | basic | 5 full rows | 2.67-4.90/5 | 9.8-28.7 s/task | Mistral/Granite strongest |
| hermes-native | reality | 6 full rows | 1.00-3.00/3 | 7.4-42.9 s/task | Mistral 3.00/3 fastest; Granite 2.95/3 |
| pi-native | basic | 5 full rows | 4.40-5.00/5 | 7.5-31.9 s/task | Mistral 5.00/5 fastest |
| pi-native | reality | 6 full rows | 1.85-3.00/3 | 5.0-35.9 s/task | Mistral and Granite 3.00/3; Mistral much faster |

The native benchmark target has been corrected: prompts should be candid user requests, while evaluator-side checks verify whether the runtime solved the use case. The previous Pi-native Mistral result should be interpreted as answer quality under over-specified prompts, not proof of spontaneous native tool use. Pi `--print` exposes no structured tool trace, and later inspection showed `tool_calls: []`. A targeted regression using the exact plain user prompt, "What is the current weather in Paris?", caused Pi/Mistral to write web-search or curl instructions instead of executing a tool; under the stricter verifier it scored 0.0 on that task. Pi-native Granite has the same caveat and had already failed Emman's manual vague-weather session.

A manual Pi session with Granite on "what is the current weather in Paris?" exposed a real failure mode in which the model returned unsynthesized search/page content and unrelated keyword summaries. A follow-up Pi/Mistral session exposed the analogous failure: it described how to use `web_search`, `web_fetch`, `curl`, or an API key, but did not actually call a tool. The corrected conclusion is that no Pi-native model is yet proven reliable for spontaneous plain-language weather tool use. These failures are not just scores; they are diagnostic artifacts that can be turned into upstream issues for the relevant runtime/model integrations.

## 7. Discussion

The strongest primary finding is that `qwen2.5-coder:7b` outperformed the larger 9B candidates on both score and latency in the raw controlled ReAct protocol. Within this task suite, format compliance and tool-use behavior mattered more than nominal model size.

The runtime-effect phase confirms that a model is not the only variable. Runtime scaffolding can rescue protocol compliance, introduce new failure modes, or both. This justifies keeping controlled-core and runtime-effect results separate.

Native platform results are meaningful because they were rerun in the clean-room runtime image with repeated independent runs and recorded binaries. They should still be interpreted differently from the primary controlled benchmark. In native mode, each platform owns tool registration, context injection, permissions, and trace visibility. Final-answer quality matters: returning raw search results, page placeholders, raw JSON, or keyword lists is a task failure when the requested behavior is a concise answer from a structured API.

The repeated gate was useful. It excluded combinations that were fast but protocol-incompatible, avoided spending full ten-run matrices on combinations that could not reliably complete a minimal tool exchange, and preserved exclusions as auditable JSON evidence.

## 8. Threats to Validity

The task corpus is small. Ten repeats provide run-level stability estimates, but broader claims require more task diversity.

The controlled runtime uses `temperature=0.0`. Zero confidence intervals in controlled-core rows are evidence of repeatability over the fixed task suite, not evidence that broader performance is known exactly.

The run used one WSL2 GPU profile on one 8 GB NVIDIA laptop GPU. Latency findings are hardware-specific.

Some tasks call Open-Meteo. One qwen3.5 smoke repeat encountered an HTTP 503 during a multi-step weather task, showing that live external dependencies can add non-model variance.

Native runtime scoring is weaker than controlled ReAct scoring because native traces are not equally structured across platforms. Pi `--print` output in particular is less transparent than a benchmark-owned ReAct transcript. The judged native-reality suite is intended to measure user-facing answer quality, but it still depends on an LLM judge. GLM 5.2 was not used as the clean-room judge because the Docker Ollama service could not authenticate to the cloud model; the run used local Mistral 7B as judge and kept GLM 5.2 only as a reference-behavior calibration.

## 9. Reproducibility

Primary commands:

```bash
docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml up -d ollama

docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml run --rm bench \
  python3 scripts/run_paper_matrix.py --phase controlled-core --with-latency-gate --force

docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/run_paper_matrix.py --phase controlled-runtime-effect --with-latency-gate --force

docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/run_paper_matrix.py --phase platform-native-basic --with-latency-gate --force

docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/run_paper_matrix.py --phase platform-native-ladder --with-latency-gate --force

docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/run_paper_matrix.py --phase platform-native-reality --with-latency-gate --force

python3 scripts/aggregate_paper_results.py
```

Generated artifacts are `results/paper-clean-room/summary.json`, `results/paper-clean-room/latency-gate-summary.json`, and `paper/clean-room-results.md`.

## 10. Conclusion

This paper reported a clean-room repeated evaluation of local LLM tool use across controlled raw-Ollama, controlled runtime-effect, and platform-native layers. The primary result is that `qwen2.5-coder:7b` was the only model to pass every controlled smoke and agentic task across ten independent repeats, while also being the fastest admitted controlled model.

The secondary result is that clean-room runtime integration matters. OpenClaw, Hermes, and Pi changed admission and score profiles in controlled ReAct mode, and their native modes produced useful deployability diagnostics that should be interpreted separately from pure model rankings. The native Pi result is now explicitly unresolved for spontaneous tool use: the exact plain weather prompt shows `mistral:7b` may plan tool use instead of doing it.

Future work should expand the task corpus, add task-level resampling, replace live API dependencies with replayable fixtures where possible, improve structured native traces, and compare text ReAct with native function calling.
