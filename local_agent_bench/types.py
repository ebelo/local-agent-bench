from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    prompt: str
    required_tools: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    requires_network: bool = False
    diagnostic_layer: str = "model"


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    ok: bool
    result: Any = None
    error: str | None = None


@dataclass
class TaskResult:
    task_id: str
    category: str
    runtime: str
    model: str
    score: float
    failure_reason: str
    final_answer: str
    tool_calls: list[ToolCall]
    latency_ms: int
    raw_transcript: list[dict[str, str]]
    assertion_results: list[dict[str, Any]] = field(default_factory=list)
    native_platform_tool_score: dict[str, Any] | None = None
