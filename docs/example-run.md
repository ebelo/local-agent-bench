# Example Run

This file shows the shape of a local smoke run without preserving user-specific paths, names, or locations.

Environment observed during the first run:

- Python: 3.12.3
- Platform: Linux WSL2
- Ollama: 0.24.0
- Ollama API: `http://localhost:11434`
- Model used for first smoke run: `qwen2.5-coder:7b`

Installed local models observed:

```text
granite4.1:3b
ibm/granite4.1:8b
qwen3.5:4b
qwen2.5-coder:7b
qwen3.5:9b
qwen3:8b
mistral:7b
mistral-nemo:latest
```

Latest smoke result summary after the benchmark semantics hardening pass:

| Task | Score | Failure reason | Tools |
| --- | ---: | --- | --- |
| `fs_current_directory` | 1.0 | `PASS` | `get_cwd` |
| `fs_list_project` | 1.0 | `PASS` | `list_directory` |
| `fs_read_fixture` | 1.0 | `PASS` | `read_file` |
| `weather_berlin_current` | 1.0 | `PASS` | `get_weather` |
| `multi_step_read_then_weather` | 1.0 | `PASS` | `read_file`, `get_weather` |

Important diagnostic note: an early implementation found a real tool-layer issue where geocoding could fail for a location string. The weather tool now includes a deterministic fallback for the smoke-test city. This is the intended benchmark behavior: tool/config failures should be identified before judging the model.

The hardening pass also found and fixed an assertion-path bug: `entries[].name` initially resolved to an empty list, which caused a false failure for the directory-listing task. The regression test now covers list expansion in tool-result assertions.
