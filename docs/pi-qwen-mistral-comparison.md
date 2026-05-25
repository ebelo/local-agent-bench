# Pi Runtime Smoke Comparison: qwen3.5:9b vs mistral:7b

Date: 2026-05-25

Runtime: `pi-react`

Benchmark: `benchmarks/smoke.json`

This comparison uses Pi Coding Agent in one-shot print mode with local Ollama models. The benchmark checks basic filesystem inspection, file reading, live weather lookup, and a multi-step read-then-weather task.

## Summary

| Model | Passed | Score | Total task latency |
| --- | ---: | ---: | ---: |
| `ollama/qwen3.5:9b` | 5/5 | 5.00/5 | 77.96 s |
| `ollama/mistral:7b` | 3/5 | 3.25/5 | 26.61 s |

`qwen3.5:9b` is the stronger Pi local-agent model in this smoke benchmark. It is slower, but it completed every task, including the multi-step workflow.

`mistral:7b` handled simple filesystem tool use, but failed the standalone weather task by calling extra forbidden tools and failed the multi-step task with no tool attempt.

## Per-Task Results

| Task | `qwen3.5:9b` | `mistral:7b` |
| --- | --- | --- |
| `fs_current_directory` | PASS | PASS |
| `fs_list_project` | PASS | PASS |
| `fs_read_fixture` | PASS | PASS |
| `weather_berlin_current` | PASS | WRONG_TOOL |
| `multi_step_read_then_weather` | PASS | NO_TOOL_ATTEMPT |

## Notes

The ReAct loop now treats a plain natural-language answer after a successful tool observation as a final answer for scoring. This avoids marking valid tool-use sequences as `INVALID_TOOL_SYNTAX` solely because the model omitted the optional `Final Answer:` prefix after observing tool output.

Raw local result JSON files are intentionally not committed. They may include machine-specific metadata and should be regenerated for local diagnostics.
