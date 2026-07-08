#!/bin/bash
set -e
cd /home/ebelo/.openclaw/workspace/projects/local-agent-bench

# Remaining runs needed:
# raw-ollama-react: smoke + agentic, runs 1,2,3 (all crashed on 503)
# pi-react: agentic run 2 (crashed), agentic run 3
# hermes-react: smoke run 3, agentic run 3
# openclaw-react: smoke run 3, agentic run 3
# pi-react: smoke run 3

declare -a JOBS=(
  "raw-ollama-react|benchmarks/smoke.json|1"
  "raw-ollama-react|benchmarks/agentic.json|1"
  "raw-ollama-react|benchmarks/smoke.json|2"
  "raw-ollama-react|benchmarks/agentic.json|2"
  "raw-ollama-react|benchmarks/smoke.json|3"
  "raw-ollama-react|benchmarks/agentic.json|3"
  "pi-react|benchmarks/agentic.json|2"
  "hermes-react|benchmarks/smoke.json|3"
  "hermes-react|benchmarks/agentic.json|3"
  "openclaw-react|benchmarks/smoke.json|3"
  "openclaw-react|benchmarks/agentic.json|3"
  "pi-react|benchmarks/smoke.json|3"
  "pi-react|benchmarks/agentic.json|3"
)

for job in "${JOBS[@]}"; do
  IFS='|' read -r RT BENCH RUN <<< "$job"
  BENCH_NAME=$(basename "$BENCH" .json)
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  OUTPUT="results/${RT}_ornith9b_${BENCH_NAME}_run${RUN}_${TIMESTAMP}.json"
  echo "=== $(date +%H:%M:%S) | $RT | $BENCH_NAME | run $RUN ==="
  python3 -m local_agent_bench run \
    --model "ornith:9b" \
    --runtime "$RT" \
    --benchmark "$BENCH" \
    --output "$OUTPUT" 2>&1 || echo "CRASHED"
  echo
done

echo "=== ALL REMAINING DONE ==="
