# Task Schema

Benchmark tasks are JSON objects. The schema is intentionally simple so new runtimes can consume the same tasks.

```json
{
  "id": "fs_list_project",
  "category": "filesystem",
  "prompt": "List the files and folders in the current project directory.",
  "required_tools": ["list_directory"],
  "allowed_tools": ["list_directory"],
  "forbidden_tools": [],
  "requires_network": false,
  "diagnostic_layer": "tool_protocol",
  "assertions": [
    {
      "type": "tool_result_contains",
      "tool": "list_directory",
      "path": "entries[].name",
      "value": "README.md"
    },
    {
      "type": "answer_contains_all",
      "values": ["README.md", "benchmarks", "local_agent_bench"]
    }
  ]
}
```

## Fields

- `id`: stable task identifier.
- `category`: broad capability area, such as `filesystem`, `weather`, or `multi_step`.
- `prompt`: the user-facing prompt sent to the model/runtime.
- `required_tools`: every tool that must be called for the task to pass.
- `allowed_tools`: optional allowlist. If set, calls outside the list are scored as wrong-tool failures.
- `forbidden_tools`: tools that must not be called.
- `requires_network`: whether the task needs external network access.
- `diagnostic_layer`: the expected layer under test, such as `tool_protocol`, `tool_execution`, or `agent_loop`.
- `assertions`: checks applied after tool execution and final answer generation.

Legacy fields `expected_tools`, `expected_contains_any`, and `expected_contains_all` are still accepted and converted on load, but new tasks should use the explicit schema above.

## Assertion Types

`answer_contains`

```json
{"type": "answer_contains", "value": "README.md"}
```

Passes when the final answer contains the given text.

`answer_contains_any`

```json
{"type": "answer_contains_any", "values": ["Berlin"]}
```

Passes when the final answer contains at least one value.

`answer_contains_all`

```json
{"type": "answer_contains_all", "values": ["README.md", "benchmarks"]}
```

Passes when the final answer contains every value.

`answer_not_contains_any`

```json
{"type": "answer_not_contains_any", "values": ["blue", "green"]}
```

Passes when the final answer contains none of the listed values.

`tool_call_count`

```json
{"type": "tool_call_count", "tool": "read_file", "min": 2, "max": 2}
```

Passes when the named tool was called within the optional minimum and maximum bounds.

`tool_call_sequence`

```json
{"type": "tool_call_sequence", "tools": ["read_file", "get_weather"]}
```

Passes when the observed tool calls contain the expected sequence in order. Extra calls before, between, or after the expected calls are allowed unless restricted by `allowed_tools`, `forbidden_tools`, or `tool_call_count`.

`tool_call_failed`

```json
{"type": "tool_call_failed", "tool": "read_file"}
```

Passes when the named tool had at least one failed call. This is useful for recovery tasks where an initial failure is intentional and should not make the whole task fail if the agent recovers.

`tool_result_contains`

```json
{
  "type": "tool_result_contains",
  "tool": "list_directory",
  "path": "entries[].name",
  "value": "README.md"
}
```

Passes when a successful tool call produced the expected value at the given result path.

`answer_contains_tool_result`

```json
{
  "type": "answer_contains_tool_result",
  "tool": "get_weather",
  "path": "temperature_c"
}
```

Passes when the final answer includes a value that came from a successful tool result. This reduces false passes where the model called a tool but ignored the observation.

## Result Paths

Paths are dot-separated. `[]` expands a list.

Example tool result:

```json
{
  "entries": [
    {"name": "README.md"},
    {"name": "tests"}
  ]
}
```

The path `entries[].name` resolves to:

```json
["README.md", "tests"]
```
