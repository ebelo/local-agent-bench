from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ToolError(RuntimeError):
    pass


def _safe_path(path: str) -> Path:
    candidate = (PROJECT_ROOT / path).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ToolError(f"path escapes project root: {path}") from exc
    return candidate


def get_cwd() -> dict[str, str]:
    return {"cwd": str(PROJECT_ROOT)}


def list_directory(path: str = ".") -> dict[str, Any]:
    directory = _safe_path(path)
    if not directory.exists():
        raise ToolError(f"path does not exist: {path}")
    if not directory.is_dir():
        raise ToolError(f"path is not a directory: {path}")
    entries = sorted(
        (
            {
                "name": child.name,
                "type": "directory" if child.is_dir() else "file",
            }
            for child in directory.iterdir()
        ),
        key=lambda entry: entry["name"],
    )
    return {"path": str(directory), "entries": entries}


def read_file(path: str) -> dict[str, str]:
    file_path = _safe_path(path)
    if not file_path.exists():
        raise ToolError(f"path does not exist: {path}")
    if not file_path.is_file():
        raise ToolError(f"path is not a file: {path}")
    return {"path": str(file_path), "content": file_path.read_text(encoding="utf-8")}


def get_weather(location: str) -> dict[str, Any]:
    coordinates = resolve_location(location)
    weather = _open_meteo(coordinates["latitude"], coordinates["longitude"])
    current = weather["current"]
    return {
        "location": coordinates["name"],
        "country": coordinates.get("country"),
        "latitude": coordinates["latitude"],
        "longitude": coordinates["longitude"],
        "time": current["time"],
        "temperature_c": current["temperature_2m"],
        "relative_humidity_percent": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
    }


def resolve_location(location: str) -> dict[str, Any]:
    return _geocode(location)


def fetch_weather(latitude: float, longitude: float) -> dict[str, Any]:
    return _open_meteo(latitude, longitude)


def _geocode(location: str) -> dict[str, Any]:
    normalized = location.casefold()
    for key, coordinates in KNOWN_LOCATIONS.items():
        if key in normalized:
            return coordinates

    query = urllib.parse.urlencode({"name": location, "count": 1, "language": "en", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{query}"
    data = _get_json(url)
    results = data.get("results") or []
    if not results:
        raise ToolError(f"could not geocode location: {location}")
    return results[0]


def _open_meteo(latitude: float, longitude: float) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
            "timezone": "auto",
        }
    )
    return _get_json(f"https://api.open-meteo.com/v1/forecast?{query}")


def _get_json(url: str) -> dict[str, Any]:
    timeout = float(os.environ.get("LOCAL_AGENT_BENCH_HTTP_TIMEOUT", "20"))
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


ToolFn = Callable[..., dict[str, Any]]

TOOLS: dict[str, ToolFn] = {
    "get_cwd": get_cwd,
    "list_directory": list_directory,
    "read_file": read_file,
    "get_weather": get_weather,
}

KNOWN_LOCATIONS: dict[str, dict[str, Any]] = {
    "berlin": {
        "name": "Berlin",
        "country": "Germany",
        "latitude": 52.52,
        "longitude": 13.405,
    },
    "zurich": {
        "name": "Zurich",
        "country": "Switzerland",
        "latitude": 47.3769,
        "longitude": 8.5417,
    },
    "zürich": {
        "name": "Zurich",
        "country": "Switzerland",
        "latitude": 47.3769,
        "longitude": 8.5417,
    },
}


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name not in TOOLS:
        raise ToolError(f"unknown tool: {name}")
    return TOOLS[name](**args)


def tool_descriptions() -> str:
    return "\n".join(
        [
            '- get_cwd: get the project root. args: {}',
            '- list_directory: list files/folders under the project root. args: {"path": "."}',
            '- read_file: read a UTF-8 file under the project root. args: {"path": "benchmarks/fixtures.md"}; use the requested path when one is provided',
            '- get_weather: get current weather through Open-Meteo. args: {"location": "Berlin, Germany"}',
        ]
    )
