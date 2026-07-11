# Clean-Room Result Summary

Dataset: `clean-room-2026-07`
Result directory: `/home/ebelo/.openclaw/workspace/projects/local-agent-bench/results/paper-clean-room`
Execution profile(s): `docker-compose.wsl-gpu, docker-compose.wsl-gpu.agent-runtimes`
Loaded benchmark runs: `397` from `397` benchmark JSON files
Latency gate result files: `183`

## Latency Gate

Evaluated gates: `61`; excluded combinations: `20`

| Phase | Runtime | Model | Latency | Reason |
|---|---|---|---:|---|
| controlled-runtime-effect | openclaw-react | qwen2.5-coder:7b | 7.4s | 0/3 gate attempts passed; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90 |
| controlled-runtime-effect | openclaw-react | qwen3.5:9b | 68.2s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-runtime-effect | openclaw-react | ornith:9b | 4.6s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-runtime-effect | openclaw-react | lfm2.5:latest | 11.3s | 0/3 gate attempts passed; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90 |
| controlled-runtime-effect | openclaw-react | ibm/granite4.1:8b | 4.2s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-runtime-effect | hermes-react | qwen3.5:9b | 6.9s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90 |
| controlled-runtime-effect | hermes-react | ornith:9b | 4.9s | 1/3 gate attempts passed; latency 11.0s <= 120.0s and score 1.00; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90 |
| controlled-runtime-effect | hermes-react | lfm2.5:latest | 12.6s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.50 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-runtime-effect | hermes-react | ibm/granite4.1:8b | 4.2s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-runtime-effect | pi-react | qwen3.5:9b | 6.6s | 0/3 gate attempts passed; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-runtime-effect | pi-react | ornith:9b | 4.0s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.75 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-runtime-effect | pi-react | mistral:7b | 1.9s | 1/3 gate attempts passed; latency 3.3s <= 120.0s and score 1.00; score 0.00 below gate minimum 0.90; score 0.25 below gate minimum 0.90 |
| controlled-runtime-effect | pi-react | lfm2.5:latest | 14.5s | 1/3 gate attempts passed; latency 14.5s <= 120.0s and score 1.00; score 0.50 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-runtime-effect | pi-react | ibm/granite4.1:8b | 2.0s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| platform-native-basic | hermes-native | qwen3.5:9b | 6.3s | 1/3 gate attempts passed; latency 9.9s <= 120.0s and score 1.00; score 0.50 below gate minimum 0.90; score 0.50 below gate minimum 0.90 |
| platform-native-basic | pi-native | qwen2.5-coder:7b | 1.7s | 1/3 gate attempts passed; score 0.50 below gate minimum 0.90; score 0.50 below gate minimum 0.90; latency 1.7s <= 120.0s and score 1.00 |
| platform-native-ladder | pi-native | ornith:9b | 6.3s | 1/3 gate attempts passed; score 0.50 below gate minimum 0.90; latency 6.3s <= 120.0s and score 1.00; score 0.50 below gate minimum 0.90 |
| controlled-core | raw-ollama-react | mistral:7b | 1.7s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |
| controlled-core | raw-ollama-react | lfm2.5:latest | 7.6s | 0/3 gate attempts passed; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90; score 0.25 below gate minimum 0.90 |
| controlled-core | raw-ollama-react | ibm/granite4.1:8b | 1.5s | 0/3 gate attempts passed; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90; score 0.00 below gate minimum 0.90 |

## controlled-core

| Runtime | Model | Benchmark | Runs | Mean Score | 95% CI | Avg s/task | Main Failures |
|---|---|---|---:|---:|---:|---:|---|
| raw-ollama-react | ornith:9b | agentic | 10 | 4.25/5 | ±0.00 | 7.7 | PASS=40, MISSING_REQUIRED_TOOL=10 |
| raw-ollama-react | ornith:9b | smoke | 10 | 3.50/5 | ±0.00 | 8.7 | PASS=30, MISSING_REQUIRED_TOOL=10, WRONG_TOOL=10 |
| raw-ollama-react | qwen2.5-coder:7b | agentic | 10 | 5.00/5 | ±0.00 | 3.5 | PASS=50 |
| raw-ollama-react | qwen2.5-coder:7b | smoke | 10 | 5.00/5 | ±0.00 | 3.3 | PASS=50 |
| raw-ollama-react | qwen3.5:9b | agentic | 10 | 4.25/5 | ±0.00 | 12.5 | PASS=40, INVALID_TOOL_SYNTAX=10 |
| raw-ollama-react | qwen3.5:9b | smoke | 10 | 3.45/5 | ±0.11 | 12.1 | PASS=29, WRONG_TOOL=20, TOOL_EXECUTION_FAILED=1 |

## controlled-runtime-effect

| Runtime | Model | Benchmark | Runs | Mean Score | 95% CI | Avg s/task | Main Failures |
|---|---|---|---:|---:|---:|---:|---|
| hermes-react | ollama/mistral:7b | agentic | 10 | 2.55/5 | ±0.56 | 9.6 | PASS=20, NO_TOOL_ATTEMPT=15, MISSING_REQUIRED_TOOL=4 |
| hermes-react | ollama/mistral:7b | smoke | 10 | 3.92/5 | ±0.60 | 11.0 | PASS=37, WRONG_TOOL=7, NO_TOOL_ATTEMPT=5 |
| hermes-react | ollama/qwen2.5-coder:7b | agentic | 10 | 4.28/5 | ±0.26 | 11.2 | PASS=38, ASSERTION_FAILED=7, MISSING_REQUIRED_TOOL=4 |
| hermes-react | ollama/qwen2.5-coder:7b | smoke | 10 | 4.20/5 | ±0.45 | 10.2 | PASS=38, WRONG_TOOL=7, ASSERTION_FAILED=4 |
| openclaw-react | ollama/mistral:7b | agentic | 10 | 2.60/5 | ±0.58 | 10.8 | PASS=18, NO_TOOL_ATTEMPT=11, TOOL_EXECUTION_FAILED=7 |
| openclaw-react | ollama/mistral:7b | smoke | 10 | 4.22/5 | ±0.55 | 9.1 | PASS=41, NO_TOOL_ATTEMPT=4, MISSING_REQUIRED_TOOL=3 |
| pi-react | ollama/qwen2.5-coder:7b | agentic | 10 | 4.35/5 | ±0.38 | 5.6 | PASS=39, MISSING_REQUIRED_TOOL=4, ASSERTION_FAILED=3 |
| pi-react | ollama/qwen2.5-coder:7b | smoke | 10 | 4.00/5 | ±0.25 | 4.4 | PASS=35, ASSERTION_FAILED=6, WRONG_TOOL=5 |

## platform-native-basic

| Runtime | Model | Benchmark | Runs | Mean Score | 95% CI | Avg s/task | Main Failures |
|---|---|---|---:|---:|---:|---:|---|
| hermes-native | ollama/ibm/granite4.1:8b | platform-native | 10 | 4.90/5 | ±0.23 | 20.9 | PLATFORM_NATIVE_PASS=49, PLATFORM_NATIVE_FAIL=1 |
| hermes-native | ollama/lfm2.5:latest | platform-native | 10 | 2.67/5 | ±0.81 | 28.7 | PLATFORM_NATIVE_PASS=26, PLATFORM_NATIVE_FAIL=23, PLATFORM_NATIVE_PARTIAL=1 |
| hermes-native | ollama/mistral:7b | platform-native | 10 | 4.90/5 | ±0.23 | 9.8 | PLATFORM_NATIVE_PASS=49, PLATFORM_NATIVE_FAIL=1 |
| hermes-native | ollama/ornith:9b | platform-native | 10 | 4.80/5 | ±0.30 | 22.8 | PLATFORM_NATIVE_PASS=48, PLATFORM_NATIVE_FAIL=2 |
| hermes-native | ollama/qwen2.5-coder:7b | platform-native | 10 | 4.30/5 | ±0.48 | 22.0 | PLATFORM_NATIVE_PASS=43, PLATFORM_NATIVE_FAIL=7 |
| openclaw-native | ollama/ibm/granite4.1:8b | platform-native | 3 | 0.00/5 | ±0.00 | 32.4 | PLATFORM_NATIVE_FAIL=15 |
| openclaw-native | ollama/lfm2.5:latest | platform-native | 3 | 0.00/5 | ±0.00 | 31.6 | PLATFORM_NATIVE_FAIL=15 |
| openclaw-native | ollama/mistral:7b | platform-native | 3 | 0.00/5 | ±0.00 | 18.3 | PLATFORM_NATIVE_FAIL=15 |
| openclaw-native | ollama/ornith:9b | platform-native | 3 | 0.00/5 | ±0.00 | 33.2 | PLATFORM_NATIVE_FAIL=15 |
| openclaw-native | ollama/qwen2.5-coder:7b | platform-native | 3 | 0.00/5 | ±0.00 | 21.8 | PLATFORM_NATIVE_FAIL=15 |
| openclaw-native | ollama/qwen3.5:9b | platform-native | 3 | 0.00/5 | ±0.00 | 29.3 | PLATFORM_NATIVE_FAIL=15 |
| pi-native | ollama/ibm/granite4.1:8b | platform-native | 10 | 4.80/5 | ±0.30 | 20.4 | PLATFORM_NATIVE_PASS=48, PLATFORM_NATIVE_FAIL=2 |
| pi-native | ollama/lfm2.5:latest | platform-native | 10 | 4.65/5 | ±0.41 | 23.2 | PLATFORM_NATIVE_PASS=46, PLATFORM_NATIVE_FAIL=3, PLATFORM_NATIVE_PARTIAL=1 |
| pi-native | ollama/mistral:7b | platform-native | 10 | 5.00/5 | ±0.00 | 7.5 | PLATFORM_NATIVE_PASS=50 |
| pi-native | ollama/ornith:9b | platform-native | 10 | 4.40/5 | ±0.60 | 31.9 | PLATFORM_NATIVE_PASS=44, PLATFORM_NATIVE_FAIL=6 |
| pi-native | ollama/qwen3.5:9b | platform-native | 10 | 4.80/5 | ±0.30 | 26.7 | PLATFORM_NATIVE_PASS=48, PLATFORM_NATIVE_FAIL=2 |

## platform-native-reality

| Runtime | Model | Benchmark | Runs | Mean Score | 95% CI | Avg s/task | Main Failures |
|---|---|---|---:|---:|---:|---:|---|
| hermes-native | ollama/ibm/granite4.1:8b | platform-native-reality | 10 | 2.95/3 | ±0.08 | 20.1 | PLATFORM_NATIVE_PASS=28, PLATFORM_NATIVE_PARTIAL=2 |
| hermes-native | ollama/lfm2.5:latest | platform-native-reality | 10 | 1.00/3 | ±0.34 | 28.7 | PLATFORM_NATIVE_FAIL=20, PLATFORM_NATIVE_PASS=10 |
| hermes-native | ollama/mistral:7b | platform-native-reality | 10 | 3.00/3 | ±0.00 | 7.4 | PLATFORM_NATIVE_PASS=30 |
| hermes-native | ollama/ornith:9b | platform-native-reality | 10 | 2.70/3 | ±0.35 | 22.0 | PLATFORM_NATIVE_PASS=27, PLATFORM_NATIVE_FAIL=3 |
| hermes-native | ollama/qwen2.5-coder:7b | platform-native-reality | 10 | 2.33/3 | ±0.30 | 16.4 | PLATFORM_NATIVE_PASS=21, PLATFORM_NATIVE_FAIL=6, PLATFORM_NATIVE_PARTIAL=3 |
| hermes-native | ollama/qwen3.5:9b | platform-native-reality | 10 | 2.27/3 | ±0.57 | 42.9 | PLATFORM_NATIVE_PASS=22, PLATFORM_NATIVE_FAIL=7, PLATFORM_NATIVE_PARTIAL=1 |
| openclaw-native | ollama/ibm/granite4.1:8b | platform-native-reality | 3 | 0.00/3 | ±0.00 | 31.3 | PLATFORM_NATIVE_FAIL=9 |
| openclaw-native | ollama/lfm2.5:latest | platform-native-reality | 3 | 0.00/3 | ±0.00 | 29.1 | PLATFORM_NATIVE_FAIL=9 |
| openclaw-native | ollama/mistral:7b | platform-native-reality | 3 | 0.00/3 | ±0.00 | 17.7 | PLATFORM_NATIVE_FAIL=9 |
| openclaw-native | ollama/ornith:9b | platform-native-reality | 3 | 0.33/3 | ±1.43 | 23.3 | PLATFORM_NATIVE_FAIL=8, PLATFORM_NATIVE_PASS=1 |
| openclaw-native | ollama/qwen2.5-coder:7b | platform-native-reality | 3 | 0.00/3 | ±0.00 | 22.4 | PLATFORM_NATIVE_FAIL=9 |
| openclaw-native | ollama/qwen3.5:9b | platform-native-reality | 3 | 0.00/3 | ±0.00 | 23.8 | PLATFORM_NATIVE_FAIL=9 |
| pi-native | ollama/ibm/granite4.1:8b | platform-native-reality | 10 | 3.00/3 | ±0.00 | 26.5 | PLATFORM_NATIVE_PASS=30 |
| pi-native | ollama/lfm2.5:latest | platform-native-reality | 10 | 2.40/3 | ±0.50 | 30.7 | PLATFORM_NATIVE_PASS=24, PLATFORM_NATIVE_FAIL=6 |
| pi-native | ollama/mistral:7b | platform-native-reality | 10 | 3.00/3 | ±0.00 | 5.0 | PLATFORM_NATIVE_PASS=30 |
| pi-native | ollama/ornith:9b | platform-native-reality | 10 | 2.80/3 | ±0.30 | 30.7 | PLATFORM_NATIVE_PASS=28, PLATFORM_NATIVE_FAIL=2 |
| pi-native | ollama/qwen2.5-coder:7b | platform-native-reality | 10 | 1.85/3 | ±0.41 | 15.4 | PLATFORM_NATIVE_PASS=17, PLATFORM_NATIVE_FAIL=11, PLATFORM_NATIVE_PARTIAL=2 |
| pi-native | ollama/qwen3.5:9b | platform-native-reality | 10 | 2.80/3 | ±0.45 | 35.9 | PLATFORM_NATIVE_PASS=28, PLATFORM_NATIVE_FAIL=2 |

## unknown

| Runtime | Model | Benchmark | Runs | Mean Score | 95% CI | Avg s/task | Main Failures |
|---|---|---|---:|---:|---:|---:|---|
| openclaw-native | ollama/qwen2.5-coder:7b | platform_native | 1 | 0.00/5 | ±0.00 | 24.7 | PLATFORM_NATIVE_FAIL=5 |

