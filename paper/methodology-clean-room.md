# Clean-Room Methodology

This note defines the reproducibility procedure for paper-grade Local Agent Bench results.

## Goal

The paper dataset must be generated from a clean, explicit execution profile rather than from a long-lived personal laptop workspace. The clean-room run should make it clear which results are:

- primary controlled evidence,
- secondary runtime-effect evidence,
- platform-native diagnostic evidence,
- exploratory or excluded legacy evidence.

## Clean Environment

Use Docker Compose as the default clean-room profile:

```bash
docker compose up -d ollama
docker compose run --rm bench python3 -m pytest -q
```

The default profile does not publish Ollama on the host. This keeps the paper run isolated from any laptop-level Ollama already listening on `localhost:11434`; the benchmark container reaches the clean Ollama service at `http://ollama:11434` on the compose network. If host API access is needed for debugging, use:

```bash
docker compose -f docker-compose.yml -f docker-compose.host-port.yml up -d ollama
```

The default compose file does not request a GPU, so it starts on CPU-only Docker hosts and on hosts where Docker cannot see the GPU runtime. For a GPU-backed clean-room run, use the explicit override and record it in the run notes:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d ollama
```

On WSL2 hosts where `nvidia-smi` works in WSL but Docker is not configured with the NVIDIA runtime, use the WSL2-specific override instead:

```bash
docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml up -d ollama
```

If the GPU override fails, do not silently mix environments. Either fix the Docker GPU runtime and rerun, or proceed with the CPU-only clean-room profile and let the latency gate exclude model/runtime combinations that are not usable under that profile.

The compose profiles stamp `metadata.execution_profile` into each result JSON. Expected values are `docker-compose.cpu`, `docker-compose.gpu`, and `docker-compose.wsl-gpu`; do not mix profiles inside one paper result directory unless the profile distinction is part of the reported comparison.

For OpenClaw, Hermes, and Pi phases, add the runtime overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/setup_runtime_clean_room.py
```

The runtime overlay installs pinned binaries into the benchmark image: OpenClaw `2026.6.11`, Pi `0.80.3`, Hermes from `NousResearch/hermes-agent` at `f64e4f4f5768c18a53f44890747653bafcab2796`, and Node.js `26.1.0`. Runtime homes are set to throwaway `/tmp/local-agent-bench-*` paths, and `scripts/setup_runtime_clean_room.py` writes clean provider/model configuration against the compose Ollama service.

Pull every model named in `paper/clean-room-matrix.json` before running the matrix:

```bash
docker compose exec ollama ollama pull qwen2.5-coder:7b
docker compose exec ollama ollama pull qwen3.5:9b
docker compose exec ollama ollama pull ornith:9b
docker compose exec ollama ollama pull mistral:7b
docker compose exec ollama ollama pull lfm2.5:latest
docker compose exec ollama ollama pull ibm/granite4.1:8b
```

The Ollama image tag is pinned through `OLLAMA_IMAGE` in `docker-compose.yml`. Before a paper rerun, record the resolved image digest:

```bash
docker image inspect "${OLLAMA_IMAGE:-ollama/ollama:0.31.1}" --format '{{index .RepoDigests 0}}'
```

## Primary Paper Dataset

The primary dataset is the `controlled-core` phase:

```bash
docker compose run --rm bench \
  python3 scripts/run_paper_matrix.py \
  --manifest paper/clean-room-matrix.json \
  --phase controlled-core \
  --with-latency-gate
```

This phase uses:

- `raw-ollama-react`,
- the benchmark-owned ReAct prompt,
- benchmark-owned deterministic tools,
- `temperature=0.0`,
- ten independent process runs per model and benchmark,
- a 30-second per-task usability threshold.

This is the only dataset that should carry strong cross-model claims unless later phases are rerun under the same clean profile and included explicitly. A single completed pass is only a pilot/sanity check; paper claims should use the full repeated-run matrix so the generated tables include variance and confidence intervals.

The repeated runs measure execution stability under the declared clean profile. Because the controlled ReAct runs use `temperature=0.0`, some models may produce identical scores across all repeats and therefore show a zero run-level confidence interval. That supports repeatability claims for this task suite, but it is not by itself a claim of generalization to the broader universe of agent tasks; broader statistical claims require a larger task corpus or task-level resampling.

The latency gate first warms each model through the Ollama API with a tiny response request, then runs `benchmarks/latency_gate.json` three times per selected phase/runtime/model before the real benchmark files. The gate requires a minimal ReAct tool round-trip (`get_cwd`, then a final answer containing the observed working directory), uses up to two model turns, and defaults to a 20-second controlled-core threshold. Admission requires at least two successful gate attempts out of three. If the warmed tool round-trip is already slow, times out, or fails the assertions in at least two attempts, the runner records the exclusion in `results/paper-clean-room/latency-gate-summary.json` and skips that model/runtime combination for the selected phase.

This separates cold model-load time from steady-state task latency. Warmup elapsed time is still recorded in the latency-gate summary, so the paper can report cold-start concerns separately without letting one-time loading dominate every task table.

Latency-gate exclusions are a pre-registered exclusion criterion, not a hidden cleanup step. Excluded model/runtime combinations must remain visible in `latency-gate-summary.json` and in the generated Markdown summary, and the paper should state that rankings apply only to combinations that passed this first-turn usability gate.

## Secondary Runtime Evidence

The `controlled-runtime-effect` phase can be run when OpenClaw, Hermes, and Pi are installed inside the same clean profile or in separate clean runtime images:

```bash
docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/run_paper_matrix.py \
  --manifest paper/clean-room-matrix.json \
  --phase controlled-runtime-effect \
  --with-latency-gate
```

These results answer whether runtime prompt structuring changes controlled ReAct performance. They are secondary evidence rather than the primary model ranking, and they may be included when the runtime binaries and generated configs are recorded.

## Platform-Native Evidence

The native phases answer a different question: whether a platform/model combination completes useful tasks when the user asks naturally, as they would ask a cloud model.

```bash
docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/run_paper_matrix.py \
  --manifest paper/clean-room-matrix.json \
  --phase platform-native-basic \
  --with-latency-gate
```

Native results are diagnostic evidence, not pure model rankings. They depend on runtime tool registration, context injection, model allowlists, and trace visibility. Pi `--print` output is especially weaker than a structured tool trace, so native claims must stay cautious.

Native prompts must be candid user requests. Do not put evaluator hints such as "use curl", endpoint URLs, "structured API", "Evidence line", or "do not dump raw JSON" into the user prompt. Those are benchmark-side expectations, not user behavior. The evaluator may still require current data, concise synthesis, source hygiene, and no plan-only text.

The full native phases must use LLM judging plus deterministic guardrails. Deterministic native scoring is reserved for cheap latency/admission gates and hard guardrails, because fragment matching can overstate real usability when a model returns raw search results, placeholder-heavy page scrapes, or unrelated keyword lists instead of a synthesized answer. A native run only counts as user-facing evidence when the final answer directly satisfies the candid prompt a user would have typed into that runtime.

For runtimes without structured tool traces, do not claim that a tool was actually called solely because the final answer names a source, contains a command, or reports a plausible value. Weather tasks must include plain user prompts such as "What is the current weather in Paris?", critical plan-language rejection, and an independent live-value verifier. If a model merely explains how it would call a tool, that is a runtime/model failure worth reporting upstream.

The `platform-native-reality` phase is the user-facing native regression suite. Its prompts are deliberately simple. Its hidden expectations follow a frontier-reference pattern checked with `ollama/glm-5.2:cloud`: avoid general web search when a structured source is appropriate, use a keyless structured weather API such as Open-Meteo or wttr.in, parse the current fields, and produce a short answer. The clean-room rerun uses a local `ollama/mistral:7b` judge because the Docker Ollama service could not authenticate the GLM cloud model; GLM 5.2 remains reference-behavior calibration, not primary scoring evidence.

The same hidden API-first expectation applies to weather tasks in `platform-native-basic` and `platform-native-ladder`: native weather evidence should come from structured HTTP/API calls, not general search pages or scraped weather sites. The user prompt itself remains candid.

Native full-run phases use a futility gate to avoid wasting compute on combinations that are already clearly noncompetitive. After three completed full runs, remaining repeats are skipped if the maximum observed total score is at or below 1.0. These skips are written to `results/paper-clean-room/futility-summary.json` and must be reported separately from latency-gate exclusions.

```bash
docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/run_paper_matrix.py \
  --manifest paper/clean-room-matrix.json \
  --phase platform-native-reality \
  --with-latency-gate
```

The harder ladder phase should be interpreted only as a ceiling probe:

```bash
docker compose -f docker-compose.yml -f docker-compose.wsl-gpu.yml -f docker-compose.runtimes.yml run --rm bench \
  python3 scripts/run_paper_matrix.py \
  --manifest paper/clean-room-matrix.json \
  --phase platform-native-ladder \
  --with-latency-gate
```

## Aggregation

All paper tables must be generated from JSON result files:

```bash
docker compose run --rm bench \
  python3 scripts/aggregate_paper_results.py \
  --manifest paper/clean-room-matrix.json
```

This writes:

- `results/paper-clean-room/summary.json`
- `paper/clean-room-results.md`

Do not manually edit paper result tables. If a table is wrong, fix the manifest, rerun, or fix the aggregator.

## Inclusion And Exclusion Rules

Only files under `results/paper-clean-room/` belong to the paper dataset by default.

Legacy files under `results/` remain useful for engineering history, but they are excluded unless copied into the clean-room result directory with a note explaining why.

Exclude and rerun any task file affected by:

- Open-Meteo or external API outage,
- runtime binary crash before a JSON file is written,
- wrong model tag,
- changed benchmark file after the run,
- changed code commit after the run.

Benchmark task failures are not exclusions. A model scoring `0/5` is valid evidence if the JSON result file was produced by the clean matrix.

## Paper Rewrite Implications

The rewritten paper should use this structure:

1. Introduction: local agent failures are layered, not just model failures.
2. Method: controlled ReAct protocol, benchmark tools, clean Docker profile, result manifest.
3. Results: primary controlled-core tables generated from clean JSON.
4. Runtime diagnostics: OpenClaw/Hermes/Pi results as secondary evidence when generated with the clean runtime overlay.
5. Platform-native use cases: treated as usability diagnostics with weaker trace evidence.
6. Threats to validity: single hardware class, model quantization, live APIs, runtime versions, LLM judge dependence, and missing structured native traces.
