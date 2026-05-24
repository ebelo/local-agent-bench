from __future__ import annotations

import json
from pathlib import Path

from local_agent_bench.types import Task


def load_tasks(path: Path) -> list[Task]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Task(
            id=item["id"],
            category=item["category"],
            prompt=item["prompt"],
            required_tools=list(item.get("required_tools", item.get("expected_tools", []))),
            allowed_tools=list(item.get("allowed_tools", [])),
            forbidden_tools=list(item.get("forbidden_tools", [])),
            assertions=_assertions(item),
            requires_network=bool(item.get("requires_network", False)),
            diagnostic_layer=item.get("diagnostic_layer", "model"),
        )
        for item in data["tasks"]
    ]


def _assertions(item: dict[str, object]) -> list[dict[str, object]]:
    assertions = list(item.get("assertions", []))
    contains_any = item.get("expected_contains_any", [])
    contains_all = item.get("expected_contains_all", [])
    if contains_any:
        assertions.append({"type": "answer_contains_any", "values": contains_any})
    if contains_all:
        assertions.append({"type": "answer_contains_all", "values": contains_all})
    return assertions
