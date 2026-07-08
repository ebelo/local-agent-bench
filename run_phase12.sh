#!/bin/bash
set -e
cd /home/ebelo/.openclaw/workspace/projects/local-agent-bench

MODELS_RAW=("qwen2.5-coder:7b" "mistral:7b" "ibm/granite4.1:8b" "lfm2.5:latest")
MODELS_OC=("ollama/qwen2.5-coder:7b" "ollama/mistral:7b" "ollama/ibm/granite4.1:8b" "ollama/lfm2.5:latest")

run() {
  local RT=$1 BENCH=$2 RUN=$3 MODEL=$4 TAG=$5
  local BENCH_NAME=$(basename "$BENCH" .json)
  local TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  local OUTPUT="results/${RT}_${TAG}_${BENCH_NAME}_final_run${RUN}_${TIMESTAMP}.json"
  echo "$(date +%H:%M:%S) | $RT | $TAG | $BENCH_NAME | run $RUN"
  python3 -m local_agent_bench run \
    --model "$MODEL" \
    --runtime "$RT" \
    --benchmark "$BENCH" \
    --output "$OUTPUT" 2>&1 || echo "(non-zero exit, expected for partial passes)"
  echo
}

echo "============================================"
echo "PHASE 1: raw-ollama-react (1 smoke + 1 agentic per model)"
echo "============================================"
for i in 0 1 2 3; do
  M="${MODELS_RAW[$i]}"
  T=$(echo "$M" | sed 's/:.*//' | sed 's/\//_/')
  run raw-ollama-react benchmarks/smoke.json 1 "$M" "${T}"
  run raw-ollama-react benchmarks/agentic.json 1 "$M" "${T}"
done

echo "============================================"
echo "PHASE 2: openclaw-react (3 smoke + 3 agentic per model)"
echo "============================================"
for i in 0 1 2 3; do
  M="${MODELS_OC[$i]}"
  T=$(echo "${MODELS_RAW[$i]}" | sed 's/:.*//' | sed 's/\//_/')
  for r in 1 2 3; do
    run openclaw-react benchmarks/smoke.json $r "$M" "${T}"
  done
  for r in 1 2 3; do
    run openclaw-react benchmarks/agentic.json $r "$M" "${T}"
  done
done

echo "=== ALL PHASE 1+2 RUNS COMPLETE ==="
