from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class OllamaError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OllamaClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def list_models(self) -> list[str]:
        data = self._request("GET", "/api/tags")
        return [model["name"] for model in data.get("models", [])]

    def chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        data = self._request("POST", "/api/chat", payload)
        return data.get("message", {}).get("content", "")

    def show_model(self, model: str) -> dict[str, Any]:
        return self._request("POST", "/api/show", {"model": model})

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        import os
        timeout = int(os.getenv("OLLAMA_TIMEOUT", "60"))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(f"HTTP {exc.code}: {body}", status_code=exc.code, body=body) from exc
        except urllib.error.URLError as exc:
            raise OllamaError(str(exc)) from exc
