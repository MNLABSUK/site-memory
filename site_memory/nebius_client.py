"""Nebius Token Factory client (OpenAI-compatible) with dry-run fallback.

Carried over from Trade Memory: the httpx POST to /chat/completions, JSON-fence
parsing and the "fall back to local heuristics on error" pattern. New here: one
generic ``chat_json`` used by every Site Memory task, JSON mode, thinking off
for fast door-step answers, a per-task model (Nemotron 3 Super for the nightly
pass), and an outbound privacy guard that strips anything secret-shaped plus
every vault plaintext before a request leaves the Mac.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Iterable

import httpx

from site_memory.config import get_settings
from site_memory.redact import scrub

# Tests can swap in httpx.MockTransport to capture exactly what would be sent.
TRANSPORT: httpx.AsyncBaseTransport | None = None


def parse_json_content(content: str) -> dict[str, Any]:
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def guard_outbound(text: str, forbidden: Iterable[str] = ()) -> str:
    """Remove secret-shaped strings and any known vault plaintext."""
    out = scrub(text)
    for secret in sorted({s for s in forbidden if s and len(s) >= 3}, key=len, reverse=True):
        out = out.replace(secret, "[vault]")
    return out


async def chat_json(
    task: str,
    system: str,
    payload: dict[str, Any],
    *,
    model: str | None = None,
    max_tokens: int = 900,
    temperature: float = 0.2,
    forbidden: Iterable[str] = (),
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Returns (parsed_json | None, meta). None means: use the local heuristic."""
    s = get_settings()
    use_model = model or s["model"]
    meta: dict[str, Any] = {"task": task, "model": use_model, "source": "dry-run"}
    if s["dry_run"]:
        meta["reason"] = "NEBIUS_API_KEY not set"
        return None, meta
    user = guard_outbound(json.dumps(payload, ensure_ascii=False), forbidden)
    body = {
        "model": use_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Authorization": f"Bearer {s['api_key']}", "Content-Type": "application/json"}
    t0 = time.perf_counter()
    try:
        # Stay under the UI's 75 s timeout so a slow call falls back instead of spinning.
        timeout = float(os.getenv("SITE_MEMORY_LLM_TIMEOUT") or 55)
        async with httpx.AsyncClient(timeout=timeout, transport=TRANSPORT) as client:
            resp = await client.post(f"{s['base_url']}/chat/completions", headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"].get("content") or ""
        parsed = parse_json_content(content)
        usage = data.get("usage") or {}
        meta.update(
            source="nebius",
            latency_ms=int((time.perf_counter() - t0) * 1000),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            response_id=data.get("id"),
        )
        return parsed, meta
    except Exception as exc:  # network, HTTP, or JSON trouble: stay useful at the door
        meta.update(source="dry-run-fallback", error=f"{type(exc).__name__}: {str(exc)[:160]}",
                    latency_ms=int((time.perf_counter() - t0) * 1000))
        return None, meta
