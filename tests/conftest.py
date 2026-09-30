"""Tests run in dry-run by default (no key) on a throwaway data dir.

Set SITE_MEMORY_LIVE=1 to also run the one real Nemotron call in test_live.py.
"""

from __future__ import annotations

import os

_LIVE = os.getenv("SITE_MEMORY_LIVE") == "1"
if not _LIVE:
    os.environ["NEBIUS_API_KEY"] = ""  # set before site_memory.config loads .env (dotenv won't override)
os.environ["SITE_MEMORY_NIGHTLY_AT"] = "off"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from site_memory import memory as mem  # noqa: E402


@pytest.fixture()
def store(tmp_path, monkeypatch):
    if _LIVE:
        monkeypatch.setenv("NEBIUS_API_KEY", "")  # only test_live.py talks to Token Factory
    s = mem.MemoryStore(tmp_path / "data")
    mem.set_store(s)
    yield s
    mem.set_store(None)  # type: ignore[arg-type]


@pytest.fixture()
def client(store):
    from site_memory.app import app

    with TestClient(app) as c:
        yield c
