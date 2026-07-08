#!/bin/bash
set -e
cd /home/ebelo/.openclaw/workspace/projects/local-agent-bench

RUNTIMES="raw-ollama-react hermes-react openclaw-react pi-react"
BENCHMARKS="benchmarks/smoke.json benchmarks/agentic.json"
MODEL="ollama/ornith:9b"
# raw-ollama doesn't need the ollama/ prefix but it tolerates it

for RUN in 1 2 3; do
  for BENCH in $BENCHMARKS; do
    for RT in $RUNTIMES; do
      BENCH_NAME=$(basename "$BENCH" .json)
      TIMESTAMP=$(date +%Y%m%d_%H%M%S)
      OUTPUT="results/${RT}_ornith9b_${BENCH_NAME}_run${RUN}_${TIMESTAMP}.json"
      echo "=== Run $RUN | $RT | $BENCH_NAME ==="
      python3 -m local_agent_bench run \
        --model "$MODEL" \
        --runtime "$RT" \
        --benchmark "$BENCH" \
        --output "$OUTPUT" 2>&1 || true
      echo
    done
  done
done

echo "=== ALL DONE ==="
