"""LLM-as-judge scoring for native adapter results.

Evaluates whether the model accomplished the task intent, even when it used
the platform's own tools (bash, read, curl) instead of the benchmark's tools.

Uses OpenClaw's stateless infer path with a cloud model (default: ollama/glm-5.2:cloud)
for non-deterministic, flexible evaluation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

from local_agent_bench.types import Task, TaskResult


JUDGE_PASS = "JUDGE_PASS"
JUDGE_PARTIAL = "JUDGE_PARTIAL"
JUDGE_FAIL = "JUDGE_FAIL"
JUDGE_ERROR = "JUDGE_ERROR"


def judge_native_result(
    task: Task,
    final_answer: str,
    *,
    transcript: list[dict[str, str]] | None = None,
    judge_model: str | None = None,
    openclaw_bin: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """Use an LLM judge to evaluate a native adapter result.

    Returns a dict with:
        judge_score: float (0.0, 0.25, 0.5, 0.75, 1.0)
        judge_verdict: str (JUDGE_PASS, JUDGE_PARTIAL, JUDGE_FAIL, JUDGE_ERROR)
        judge_reasoning: str
        judge_model: str
    """
    judge_model = judge_model or os.environ.get("LOCAL_AGENT_BENCH_JUDGE_MODEL", "ollama/glm-5.2:cloud")
    openclaw_bin = openclaw_bin or os.environ.get("LOCAL_AGENT_BENCH_OPENCLAW_BIN", "openclaw")

    prompt = _build_judge_prompt(task, final_answer, transcript=transcript)

    try:
        if judge_model.startswith("ollama/") and os.environ.get("LOCAL_AGENT_BENCH_JUDGE_TRANSPORT", "ollama-api") == "ollama-api":
            raw = _run_ollama_inference(judge_model, prompt, timeout)
        else:
            raw = _run_inference(openclaw_bin, judge_model, prompt, timeout)
        verdict = _parse_judge_response(raw)
        verdict["judge_model"] = judge_model
        return verdict
    except Exception as exc:
        return {
            "judge_score": 0.0,
            "judge_verdict": JUDGE_ERROR,
            "judge_reasoning": f"Judge inference failed: {exc}",
            "judge_model": judge_model,
            "judge_raw": str(exc)[:500],
        }


def judge_task_result(result: TaskResult, task: Task, **kwargs: Any) -> dict[str, Any]:
    """Convenience wrapper: judge a TaskResult object."""
    return judge_native_result(task, result.final_answer, transcript=result.raw_transcript, **kwargs)


def _build_judge_prompt(
    task: Task,
    final_answer: str,
    *,
    transcript: list[dict[str, str]] | None = None,
) -> str:
    """Build the system + user prompt for the LLM judge."""
    assertions_desc = _describe_assertions(task.assertions)
    transcript_desc = _describe_transcript(transcript)

    system = (
        "You are an expert evaluator for AI agent benchmarks. "
        "You judge whether an agent accomplished a task, regardless of which tools it used.\n\n"
        "The agent was running through a real platform (OpenClaw, Hermes, or Pi) with its own native tools "
        "(bash, read, write, exec, curl, etc.). The benchmark defines specific tools (get_cwd, list_directory, "
        "read_file, get_weather) but the platform may not have registered them. The agent may have used "
        "platform-native tools to accomplish the same goal.\n\n"
        "Evaluate based on:\n"
        "1. Did the agent accomplish the task intent for a real end user?\n"
        "2. Did the final response answer the user's question directly and coherently?\n"
        "3. Did the agent produce a correct answer based on real tool execution (not hallucination)?\n"
        "4. Did the agent use tools to get real data, or did it just guess/answer from memory?\n\n"
        "Be flexible about tool names and formats - the agent uses the platform's tools, not the benchmark's. "
        "But be strict about user-facing quality and the requested data path: if the task asks for a structured API, "
        "native HTTP, or curl-style source, then a general web search or HTML/page scrape is at best PARTIAL and usually "
        "FAIL when it avoids the requested API route. A raw search-result dump, unrelated keyword list, placeholder-heavy "
        "page scrape, raw JSON dump, or response that fails to synthesize the tool output into an answer is a FAIL even "
        "if relevant terms appear. A hallucinated answer with no tool use is also a FAIL.\n\n"
        "Respond with a JSON object:\n"
        '{"verdict": "PASS" | "PARTIAL" | "FAIL", "score": <float>, "reasoning": "<explanation>"}\n\n'
        "Keep the JSON compact: reasoning must be one short sentence, and the whole response must be under 120 words.\n\n"
        "Scoring guide:\n"
        "- 1.0 (PASS): Agent accomplished the task fully, using tools to get real data.\n"
        "- 0.75 (PARTIAL): Agent mostly accomplished the task but missed something minor.\n"
        "- 0.5 (PARTIAL): Agent attempted tools and got partial results, or used tools but the final answer was incomplete.\n"
        "- 0.25 (PARTIAL): Agent showed tool intent but didn't get useful results.\n"
        "- 0.0 (FAIL): Agent did not accomplish the task, hallucinated, didn't use tools, or returned unsynthesized tool/search output.\n"
    )

    user = (
        f"## Task\n{task.prompt}\n\n"
        f"## Expected assertions\n{assertions_desc}\n\n"
        f"## Full platform transcript\n{transcript_desc}\n\n"
        f"## Agent's full response\n```\n{final_answer[:8000]}\n```\n\n"
        "Evaluate the agent's response. Did it accomplish the task? "
        "Respond with the JSON object only."
    )

    return f"{system}\n\n{user}"


def _describe_transcript(transcript: list[dict[str, str]] | None) -> str:
    if not transcript:
        return "(not available)"
    parts = []
    for item in transcript[-6:]:
        role = item.get("role", "?")
        content = item.get("content", "")
        parts.append(f"{role}:\n{content[:4000]}")
    return "\n\n".join(parts)


def _describe_assertions(assertions: list[dict[str, Any]]) -> str:
    if not assertions:
        return "(no specific assertions)"
    lines = []
    for a in assertions:
        atype = a.get("type", "?")
        if atype == "answer_contains_any":
            lines.append(f"- Answer should contain one of: {a.get('values', [])}")
        elif atype == "answer_contains_all":
            lines.append(f"- Answer should contain all of: {a.get('values', [])}")
        elif atype == "answer_contains":
            lines.append(f"- Answer should contain: {a.get('value', '')}")
        elif atype == "answer_not_contains_any":
            lines.append(f"- Answer should not contain any of: {a.get('values', [])}")
        elif atype == "answer_matches_regex":
            lines.append(f"- Answer should match regex: {a.get('pattern', '')}")
        elif atype == "answer_word_count_at_most":
            lines.append(f"- Answer should be at most {a.get('max', '')} words")
        elif atype == "answer_matches_open_meteo_current":
            lines.append(
                "- Answer temperature should match live Open-Meteo "
                f"{a.get('field', 'temperature_2m')} within {a.get('tolerance', 2.0)} C"
            )
        elif atype == "answer_contains_tool_result":
            lines.append(f"- Answer should include tool result from {a.get('tool', '')} at {a.get('path', '')}")
        elif atype == "tool_result_contains":
            lines.append(f"- Tool {a.get('tool', '')} result should contain: {a.get('value', '')}")
        else:
            lines.append(f"- {atype}: {json.dumps(a)}")
    return "\n".join(lines)


def _run_inference(openclaw_bin: str, model: str, prompt: str, timeout: int) -> str:
    """Run inference via openclaw infer model run --local --json."""
    argv = [
        openclaw_bin,
        "infer",
        "model",
        "run",
        "--local",
        "--json",
        "--model",
        model,
        "--prompt",
        prompt,
    ]
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"openclaw infer exited {result.returncode}: {result.stderr[:500]}")

    # Strip ANSI escape codes from output
    stdout = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout)

    # Parse JSON output; openclaw may emit log lines before the JSON.
    # Find the first '{' and try to parse from there
    json_start = stdout.find('{')
    if json_start == -1:
        raise RuntimeError(f"No JSON found in output: {stdout[:500]}")

    try:
        data = json.loads(stdout[json_start:])
    except json.JSONDecodeError:
        # Try to find the end of the JSON object
        decoder = json.JSONDecoder()
        try:
            data, _ = decoder.raw_decode(stdout[json_start:])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse JSON: {exc}. Output: {stdout[json_start:json_start+500]}")

    # Extract the text response
    if isinstance(data, dict):
        # OpenClaw infer returns {"ok": true, "outputs": [{"text": "..."}]}
        if "outputs" in data:
            outputs = data["outputs"]
            if isinstance(outputs, list) and outputs:
                return outputs[0].get("text", "")
        if "text" in data:
            return data["text"]
        if "payloads" in data:
            payloads = data["payloads"]
            if isinstance(payloads, list) and payloads:
                return payloads[0].get("text", "")
        if "response" in data:
            return data["response"]
        if "content" in data:
            return data["content"]

    return str(data)


def _run_ollama_inference(model: str, prompt: str, timeout: int) -> str:
    """Run a capped local/cloud Ollama judge call directly, avoiding CLI wrapper output."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model_tag = model.split("/", 1)[1] if model.startswith("ollama/") else model
    payload = {
        "model": model_tag,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": int(os.environ.get("LOCAL_AGENT_BENCH_JUDGE_NUM_PREDICT", "192")),
            "think": False,
        },
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("LOCAL_AGENT_BENCH_OLLAMA_API_KEY") or os.environ.get("OLLAMA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama judge HTTP {exc.code}: {body[:500]}") from exc
    message = data.get("message", {}) if isinstance(data, dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    # Some models (e.g. GLM 5.2 cloud) put reasoning in 'thinking' with empty 'content'.
    # Fall back to thinking when content is empty so the judge parser can still score.
    if not content:
        thinking = message.get("thinking", "") if isinstance(message, dict) else ""
        if thinking:
            return str(thinking)
    if not content:
        raise RuntimeError(f"No Ollama judge content: {str(data)[:500]}")
    return str(content)


def _parse_judge_response(raw: str) -> dict[str, Any]:
    """Parse the LLM judge's JSON response."""
    # Strip any ANSI codes
    raw = re.sub(r'\x1b\[[0-9;]*m', '', raw)

    # Try direct JSON parse
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find and fix truncated JSON
        # Look for {"verdict": ... pattern
        match = re.search(r'\{[^{}]*"verdict"[^{}]*', raw, re.DOTALL)
        if match:
            # Try adding closing brace
            fragment = match.group(0)
            if not fragment.endswith('}'):
                fragment += '"}'
            try:
                data = json.loads(fragment)
            except json.JSONDecodeError:
                pass

        if 'data' not in dir():
            # Try broader search: find first { and attempt to parse.
            for start in range(len(raw)):
                if raw[start] == '{':
                    try:
                        data, _ = json.JSONDecoder().raw_decode(raw[start:])
                        break
                    except json.JSONDecodeError:
                        # Try fixing truncated JSON by adding closing braces
                        fragment = raw[start:].rstrip()
                        if not fragment.endswith('}'):
                            for _ in range(3):
                                fragment += '}'
                                try:
                                    data = json.loads(fragment)
                                    break
                                except json.JSONDecodeError:
                                    continue
                        if 'data' in dir():
                            break
                        continue
            else:
                # Last resort: regex extraction
                verdict_match = re.search(r'"verdict"\s*:\s*"(PASS|PARTIAL|FAIL)"', raw, re.IGNORECASE)
                score_match = re.search(r'"score"\s*:\s*([0-9.]+)', raw)
                reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)', raw)
                if verdict_match:
                    data = {
                        "verdict": verdict_match.group(1),
                        "score": float(score_match.group(1)) if score_match else 0.0,
                        "reasoning": reasoning_match.group(1) if reasoning_match else raw[:300],
                    }
                else:
                    heuristic = _heuristic_judge_response(raw)
                    if heuristic is not None:
                        return heuristic
                    return {
                        "judge_score": 0.0,
                        "judge_verdict": JUDGE_FAIL,
                        "judge_reasoning": f"Unparseable judge response interpreted as FAIL: {raw[:300]}",
                        "judge_raw": raw[:500],
                    }

    verdict = str(data.get("verdict", "FAIL")).upper()
    score = float(data.get("score", 0.0))
    reasoning = str(data.get("reasoning", ""))

    # Normalize score to allowed values
    if verdict == "PASS":
        score = max(score, 0.75)
        if score >= 0.9:
            score = 1.0
        judge_verdict = JUDGE_PASS if score >= 0.9 else JUDGE_PARTIAL
    elif verdict == "PARTIAL":
        judge_verdict = JUDGE_PARTIAL
        score = min(max(score, 0.1), 0.75)
    else:
        judge_verdict = JUDGE_FAIL
        score = 0.0

    return {
        "judge_score": score,
        "judge_verdict": judge_verdict,
        "judge_reasoning": reasoning,
        "judge_raw": raw[:1000],
    }


def _heuristic_judge_response(raw: str) -> dict[str, Any] | None:
    text = raw.casefold()
    fail_markers = [
        "does not accomplish",
        "did not accomplish",
        "not accomplish",
        "not completed",
        "not complete",
        "not satisfy",
        "fails",
        " fail",
        "incorrect",
    ]
    partial_markers = ["partially", "partial", "incomplete but", "somewhat"]
    pass_markers = ["accomplishes", "satisfies", "correctly", "pass"]
    if any(marker in text for marker in fail_markers):
        return {
            "judge_score": 0.0,
            "judge_verdict": JUDGE_FAIL,
            "judge_reasoning": f"Unstructured judge response interpreted as FAIL: {raw[:240]}",
            "judge_raw": raw[:1000],
        }
    if any(marker in text for marker in partial_markers):
        return {
            "judge_score": 0.5,
            "judge_verdict": JUDGE_PARTIAL,
            "judge_reasoning": f"Unstructured judge response interpreted as PARTIAL: {raw[:240]}",
            "judge_raw": raw[:1000],
        }
    if any(marker in text for marker in pass_markers) and "not " not in text[:120]:
        return {
            "judge_score": 1.0,
            "judge_verdict": JUDGE_PASS,
            "judge_reasoning": f"Unstructured judge response interpreted as PASS: {raw[:240]}",
            "judge_raw": raw[:1000],
        }
    return None
