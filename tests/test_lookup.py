"""Manual lookup: only make + model leave the machine; off without TAVILY_API_KEY."""

import json

import httpx

from site_memory import lookup


def _asset(store):
    for f in store.facts():
        if f["kind"] == "asset" and f.get("make") and f.get("model"):
            return f
    raise AssertionError("seed has no asset with make + model")


def test_lookup_is_off_without_key(client, store, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert client.get("/api/status").json()["lookup"] is False
    r = client.post(f"/api/facts/{_asset(store)['id']}/lookup")
    assert r.status_code == 400


def test_lookup_sends_only_make_and_model(client, store, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    lookup._cache.clear()
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content.decode())
        return httpx.Response(200, json={"answer": "It is an NVR.", "results": [
            {"title": "User manual", "url": "https://example.com/manual.pdf", "content": "Reset: hold the button 10 s."}]})

    monkeypatch.setattr(lookup, "TRANSPORT", httpx.MockTransport(handler))
    f = _asset(store)
    r = client.post(f"/api/facts/{f['id']}/lookup").json()
    assert r["ok"] and r["results"][0]["url"].startswith("https://example.com")
    assert f["model"] in r["query"]
    body = json.loads(sent[0])
    prop = store.get_property(f["property_id"])
    for private in [prop["address"], prop.get("customer") or "@@", prop.get("postcode") or "@@", *store.vault.plaintexts()]:
        assert private not in body["query"]
    assert set(body) == {"query", "search_depth", "max_results", "include_answer"}
    # second call is served from cache: no new Tavily request
    client.post(f"/api/facts/{f['id']}/lookup")
    assert len(sent) == 1
