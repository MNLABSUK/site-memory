"""Public-demo guard rails: rate limits and scheduled reset (SITE_MEMORY_DEMO=1)."""

from datetime import datetime, timedelta

from site_memory import demo


def test_demo_off_by_default(client, monkeypatch):
    monkeypatch.delenv("SITE_MEMORY_DEMO", raising=False)
    s = client.get("/api/status").json()
    assert s["demo"] is None
    for _ in range(5):
        assert client.post("/api/capture/preview", json={"text": "hello"}).status_code == 200


def test_ai_routes_are_classified():
    assert demo.is_ai_route("POST", "/api/arrive")
    assert demo.is_ai_route("POST", "/api/skills/sk-01/improve")
    assert demo.is_ai_route("POST", "/api/facts/f-0001/lookup")
    assert not demo.is_ai_route("GET", "/api/arrive")
    assert not demo.is_ai_route("POST", "/api/review/pr-0001")


def test_per_ip_ai_limit_and_global_cap(monkeypatch):
    monkeypatch.setenv("SITE_MEMORY_DEMO_AI_PER_IP", "3")
    monkeypatch.setenv("SITE_MEMORY_DEMO_AI_PER_HOUR", "5")
    rl = demo.RateLimiter()
    t = 1000.0
    assert all(rl.check("1.1.1.1", "POST", "/api/arrive", now=t + i)[0] for i in range(3))
    ok, msg, retry = rl.check("1.1.1.1", "POST", "/api/arrive", now=t + 4)
    assert not ok and "Nemotron" in msg and retry > 0
    assert rl.check("1.1.1.1", "GET", "/api/status", now=t + 5)[0]          # reads are never limited
    assert rl.check("2.2.2.2", "POST", "/api/arrive", now=t + 6)[0]
    assert rl.check("3.3.3.3", "POST", "/api/arrive", now=t + 7)[0]
    ok, msg, _ = rl.check("4.4.4.4", "POST", "/api/arrive", now=t + 8)        # hourly budget (5) used
    assert not ok and "hourly" in msg
    assert rl.check("1.1.1.1", "POST", "/api/arrive", now=t + 4000)[0]       # windows slide


def test_middleware_returns_429_in_demo_mode(client, monkeypatch):
    monkeypatch.setenv("SITE_MEMORY_DEMO", "1")
    monkeypatch.setenv("SITE_MEMORY_DEMO_WRITES_PER_IP", "2")
    demo.limiter.reset()
    try:
        s = client.get("/api/status").json()
        assert s["demo"]["reset_every_min"] == 30
        codes = [client.post("/api/capture/preview", json={"text": "x"}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        r = client.post("/api/capture/preview", json={"text": "x"})
        assert "Slow down" in r.json()["detail"] and r.headers["Retry-After"]
    finally:
        demo.limiter.reset()


def test_forwarded_ip_is_used():
    assert demo.client_ip({"x-forwarded-for": "9.9.9.9, 10.0.0.1"}, "10.0.0.1") == "9.9.9.9"
    assert demo.client_ip({}, "127.0.0.1") == "127.0.0.1"


def test_reset_clock(monkeypatch):
    monkeypatch.setenv("SITE_MEMORY_DEMO_RESET_MIN", "10")
    c = demo.ResetClock()
    t0 = datetime(2026, 10, 1, 12, 0)
    c.mark(t0)
    assert not c.due(t0 + timedelta(minutes=9))
    assert c.due(t0 + timedelta(minutes=10))


def test_demo_reset_restores_seed(client, store):
    pid = store.list_properties()[0]["id"]
    fid = store.facts(pid)[0]["id"]
    client.post(f"/api/facts/{fid}/forget")
    assert fid not in {f["id"] for f in store.facts(pid)}
    client.post("/api/demo/reset")
    assert fid in {f["id"] for f in store.facts(pid)}
