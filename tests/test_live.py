"""One real Nemotron call through Nebius Token Factory. Opt-in:

    SITE_MEMORY_LIVE=1 .venv/bin/pytest tests/test_live.py -s
"""

import asyncio
import os

import pytest

from site_memory import agent
from site_memory.config import get_settings

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.getenv("SITE_MEMORY_LIVE") != "1", reason="set SITE_MEMORY_LIVE=1 for a real Token Factory call")
def test_live_arrival_brief(store, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    from dotenv import load_dotenv

    load_dotenv(override=True)
    assert not get_settings()["dry_run"], "no NEBIUS_API_KEY in .env"
    b = asyncio.run(agent.arrival_brief(store, "I'm at 14 Oak St, what do I need to know?", refresh=True))
    s = b["summary"]
    print("\nLIVE:", s["model"], s["latency_ms"], "ms |", s["headline"])
    assert s["source"] == "nebius"
    assert s["bullets"] and all(x["cites"] for x in s["bullets"])
