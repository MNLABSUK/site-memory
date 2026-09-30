"""Manual / firmware lookup for an asset: Tavily web search + a Nemotron summary.

Only the asset's make, model and type go to Tavily (never the address, the
customer, notes or codes). Nemotron then turns the search results into two or
three doorstep tips, each pointing at the result it came from. Disabled unless
TAVILY_API_KEY is set.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

import httpx

from site_memory.nebius_client import chat_json, guard_outbound

TAVILY_URL = "https://api.tavily.com/search"
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests swap in a MockTransport
_cache: dict[str, dict] = {}

LOOKUP_SYSTEM = """You help a UK installer standing in front of a device.
You get the device (make, model, type) and web search results about it.
Return JSON: {"summary": str (one sentence: what this device is), "tips": [{"text": str, "source": int}]}.
Give 2-3 short practical tips for a site visit (manual, default reset, latest firmware, known gotchas),
each taken ONLY from the numbered result it cites in "source". If the results don't match the device, return no tips."""


def enabled() -> bool:
    return bool((os.getenv("TAVILY_API_KEY") or "").strip())


def build_query(fact: dict) -> str:
    make = (fact.get("make") or "").strip()
    model = (fact.get("model") or "").strip()
    label = (fact.get("label") or "").strip()
    kind_word = re.sub(r"\b(front|back|rear|side|garage|loft|hall|kitchen|drive|gate|\d+)\b", "", label, flags=re.I)
    parts = [make, model, kind_word.strip() if not model else ""]
    q = " ".join(p for p in parts if p)
    return re.sub(r"\s+", " ", f"{q} manual firmware").strip()


async def lookup(fact: dict, forbidden: list[str]) -> dict:
    if not (fact.get("make") or fact.get("model")):
        return {"ok": False, "message": "Add a make or model to this asset first."}
    query = guard_outbound(build_query(fact), forbidden)
    if query in _cache:
        return {**_cache[query], "cached": True}
    key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not key:
        return {"ok": False, "message": "Manual lookup is off (no TAVILY_API_KEY)."}
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=20.0, transport=TRANSPORT) as client:
            r = await client.post(TAVILY_URL, headers={"Authorization": f"Bearer {key}"},
                                  json={"query": query, "search_depth": "basic", "max_results": 5, "include_answer": True})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        return {"ok": False, "query": query, "message": f"Tavily search failed ({type(exc).__name__}). Try again."}
    results = [{"i": i + 1, "title": (x.get("title") or "")[:140], "url": x.get("url") or "", "snippet": (x.get("content") or "")[:500]}
               for i, x in enumerate((data.get("results") or [])[:5])]
    tavily_ms = int((time.perf_counter() - t0) * 1000)
    asset = {"make": fact.get("make") or "", "model": fact.get("model") or "", "type": fact.get("label") or ""}
    parsed, meta = await chat_json("manual_lookup", LOOKUP_SYSTEM, {"device": asset, "results": results}, max_tokens=500,
                                   forbidden=forbidden)
    tips, summary = [], data.get("answer") or ""
    if parsed:
        summary = str(parsed.get("summary") or summary)[:300]
        for t in parsed.get("tips") or []:
            try:
                src = int(t.get("source"))
            except (TypeError, ValueError):
                continue
            if 1 <= src <= len(results) and str(t.get("text") or "").strip():
                tips.append({"text": str(t["text"])[:240], "source": src})
    out = {"ok": True, "query": query, "summary": summary, "tips": tips[:3], "results": results,
           "tavily_ms": tavily_ms, "meta": meta}
    _cache[query] = out
    return out
