"""One real Nemotron call through Token Factory. Prints model, latency and tokens, never the key.

Usage: .venv/bin/python scripts/live_check.py
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os  # noqa: E402

os.environ.setdefault("SITE_MEMORY_DATA_DIR", tempfile.mkdtemp(prefix="site-memory-live-"))

from site_memory import agent  # noqa: E402
from site_memory.config import get_settings  # noqa: E402
from site_memory.memory import MemoryStore  # noqa: E402


async def main() -> int:
    s = get_settings()
    if s["dry_run"]:
        print("No NEBIUS_API_KEY in .env: dry-run only.")
        return 1
    store = MemoryStore()
    brief = await agent.arrival_brief(store, "I'm at 14 Oak St, what do I need to know?")
    sm = brief["summary"]
    print(json.dumps({"task": "arrival_brief", "source": sm["source"], "model": sm["model"], "latency_ms": sm["latency_ms"],
                      "headline": sm["headline"], "bullets": len(sm["bullets"]), "dropped_uncited": sm["dropped_uncited"],
                      "llm": store.last_llm()}, indent=2))
    return 0 if sm["source"] == "nebius" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
