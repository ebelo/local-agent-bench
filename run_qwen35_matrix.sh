#!/bin/bash
set -e
cd /home/ebelo/.openclaw/workspace/projects/local-agent-bench

run() {
  local RT=$1 BENCH=$2 RUN=$3 MODEL=$4
  local BENCH_NAME=$(basename "$BENCH" .json)
  local TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  local OUTPUT="results/${RT}_qwen35_9b_${BENCH_NAME}_final_run${RUN}_${TIMESTAMP}.json"
  echo "$(date +%H:%M:%S) | $RT | $BENCH_NAME | run $RUN"
  python3 -m local_agent_bench run \
    --model "$MODEL" \
    --runtime "$RT" \
    --benchmark "$BENCH" \
    --output "$OUTPUT" 2>&1 || echo "(non-zero exit, expected for partial passes)"
  echo
}

echo "=== RAW-OLLAMA-REACT: 1 run smoke + 1 run agentic ==="
run raw-ollama-react benchmarks/smoke.json 1 qwen3.5:9b
run raw-ollama-react benchmarks/agentic.json 1 qwen3.5:9b

echo "=== OPENCLAW-REACT: 3 runs smoke + 3 runs agentic ==="
for i in 1 2 3; do
  run openclaw-react benchmarks/smoke.json $i ollama/qwen3.5:9b
done
for i in 1 2 3; do
  run openclaw-react benchmarks/agentic.json $i ollama/qwen3.5:9b
done

echo "=== HERMES-REACT: 3 runs smoke + 10 runs agentic ==="
for i in 1 2 3; do
  run hermes-react benchmarks/smoke.json $i ollama/qwen3.5:9b
done
for i in $(seq 1 10); do
  run hermes-react benchmarks/agentic.json $i ollama/qwen3.5:9b
done

echo "=== PI-REACT: 6 runs smoke + 12 runs agentic ==="
for i in $(seq 1 6); do
  run pi-react benchmarks/smoke.json $i ollama/qwen3.5:9b
done
for i in $(seq 1 12); do
  run pi-react benchmarks/agentic.json $i ollama/qwen3.5:9b
done

echo "=== ALL QWEN3.5 RUNS COMPLETE ==="
