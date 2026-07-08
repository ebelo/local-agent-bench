#!/bin/bash
set -e
cd /home/ebelo/.openclaw/workspace/projects/local-agent-bench

# Run counts based on variance analysis:
# raw-ollama-react: 1 run (deterministic, temp=0)
# openclaw-react: 3 runs
# hermes-react: 3 smoke, 10 agentic
# pi-react: 6 smoke, 12 agentic

run() {
  local RT=$1 BENCH=$2 RUN=$3 MODEL=$4
  local BENCH_NAME=$(basename "$BENCH" .json)
  local TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  local OUTPUT="results/${RT}_ornith9b_${BENCH_NAME}_final_run${RUN}_${TIMESTAMP}.json"
  echo "$(date +%H:%M:%S) | $RT | $BENCH_NAME | run $RUN"
  python3 -m local_agent_bench run \
    --model "$MODEL" \
    --runtime "$RT" \
    --benchmark "$BENCH" \
    --output "$OUTPUT" 2>&1 || echo "(non-zero exit, expected for partial passes)"
  echo
}

echo "=== RAW-OLLAMA-REACT: 1 run smoke + 1 run agentic ==="
run raw-ollama-react benchmarks/smoke.json 1 ornith:9b
run raw-ollama-react benchmarks/agentic.json 1 ornith:9b

echo "=== OPENCLAW-REACT: 3 runs smoke + 3 runs agentic ==="
for i in 1 2 3; do
  run openclaw-react benchmarks/smoke.json $i ollama/ornith:9b
done
for i in 1 2 3; do
  run openclaw-react benchmarks/agentic.json $i ollama/ornith:9b
done

echo "=== HERMES-REACT: 3 runs smoke + 10 runs agentic ==="
for i in 1 2 3; do
  run hermes-react benchmarks/smoke.json $i ollama/ornith:9b
done
for i in 1 2 3 4 5 6 7 8 9 10; do
  run hermes-react benchmarks/agentic.json $i ollama/ornith:9b
done

echo "=== PI-REACT: 6 runs smoke + 12 runs agentic ==="
for i in 1 2 3 4 5 6; do
  run pi-react benchmarks/smoke.json $i ollama/ornith:9b
done
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  run pi-react benchmarks/agentic.json $i ollama/ornith:9b
done

echo "=== ALL FINAL RUNS COMPLETE ==="
