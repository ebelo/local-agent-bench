from __future__ import annotations

from pathlib import Path
from typing import Any


def redact_local_context(value: Any, project_root: Path) -> Any:
    replacements = _replacements(project_root)
    return _redact(value, replacements)


def _redact(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, replacements) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item, replacements) for item in value)
    if isinstance(value, str):
        redacted = value
        for source, target in replacements:
            redacted = redacted.replace(source, target)
        return redacted
    return value


def _replacements(project_root: Path) -> list[tuple[str, str]]:
    root = project_root.resolve()
    home = Path.home().resolve()
    paths = [
        (str(root), "<PROJECT_ROOT>"),
        (root.as_posix(), "<PROJECT_ROOT>"),
        (str(home), "<HOME>"),
        (home.as_posix(), "<HOME>"),
    ]
    return sorted(set(paths), key=lambda item: len(item[0]), reverse=True)
