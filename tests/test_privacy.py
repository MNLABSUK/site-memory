"""Simulate the live Token Factory path with a mock transport and prove that
no vault secret ever appears in an outbound request, and that uncited or
unsupported brief lines are dropped."""

import asyncio
import json

import httpx
import pytest

from site_memory import agent, nebius_client

SENT: list[str] = []


def _reply(content: dict) -> httpx.Response:
    return httpx.Response(200, json={"id": "mock", "choices": [{"message": {"content": json.dumps(content)}}],
                                     "usage": {"prompt_tokens": 10, "completion_tokens": 5}})


def handler(request: httpx.Request) -> httpx.Response:
    body = request.content.decode()
    SENT.append(body)
    system = json.loads(body)["messages"][0]["content"]
    if "arrival brief" in system:
        return _reply({"headline": "Dog, NVR moved", "bullets": [
            {"tag": "risk", "text": "Dog loose in the back garden, ring before opening the side gate", "cites": ["n-0002"]},
            {"tag": "kit", "text": "Solar panels on the roof need cleaning", "cites": ["n-0002"]},        # unsupported
            {"tag": "kit", "text": "NVR under the stairs", "cites": []},                                   # uncited
        ]})
    if "structured property memory" in system:
        return _reply({"summary": "1 camera", "facts": [{"kind": "asset", "label": "Camera", "value": "Hikvision turret", "location": "Back door"}]})
    if "route briefing" in system:
        return _reply({"headline": "3 jobs", "jobs": [{"job_id": "j-01", "prep": [{"text": "Loft via bedroom 2", "cites": ["n-0018"]}], "bring": ["ladder"]}], "due_actions": []})
    return _reply({"title": "T", "summary": "s", "job_types": ["x"], "learned_from": [], "body_md": "# T\n- [ ] a\n"})


@pytest.fixture()
def live_mock(monkeypatch):
    SENT.clear()
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key-not-real")
    monkeypatch.setattr(nebius_client, "TRANSPORT", httpx.MockTransport(handler))
    yield
    monkeypatch.setattr(nebius_client, "TRANSPORT", None)


def test_no_secret_leaves_the_machine(store, live_mock):
    async def run():
        await agent.capture(store, "12 Elm Grove: new turret over the back door. Key safe code 5519, alarm engineer code is 7391.", property_id="p-01")
        await agent.arrival_brief(store, "12 Elm Grove", refresh=True)
        await agent.nightly(store)
        await agent.learn_skill(store, "Annual alarm service", job_type="alarm-service")
    asyncio.run(run())
    assert len(SENT) == 4
    everything = "\n".join(SENT)
    for secret in store.vault.plaintexts() + ["5519", "7391"]:
        assert secret not in everything
    assert "test-key-not-real" not in everything


def test_brief_drops_uncited_and_unsupported(store, live_mock):
    b = asyncio.run(agent.arrival_brief(store, "12 Elm Grove", refresh=True))
    s = b["summary"]
    assert s["source"] == "nebius"
    texts = [x["text"] for x in s["bullets"]]
    assert any("Dog loose" in t for t in texts)
    assert not any("Solar" in t for t in texts)
    assert s["dropped_uncited"] == 2
    # rule-based safety net: the NVR conflict still surfaces with its citations
    assert any(x.get("from_rules") and "NVR" in x["text"] for x in s["bullets"])


def test_fallback_when_token_factory_fails(store, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key-not-real")
    monkeypatch.setattr(nebius_client, "TRANSPORT", httpx.MockTransport(lambda r: httpx.Response(503)))
    b = asyncio.run(agent.arrival_brief(store, "14 Oak Street", refresh=True))
    assert b["summary"]["source"] == "dry-run-fallback"
    assert b["summary"]["bullets"]
