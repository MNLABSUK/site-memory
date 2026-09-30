"""Site Memory FastAPI app: local server + web UI on 127.0.0.1."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from site_memory import __version__, agent, demo, lookup
from site_memory import skills as skillfiles
from site_memory.config import BUSINESS_NAME, get_settings
from site_memory.memory import get_store

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


# ----------------------------------------------------------------- requests
class ArriveRequest(BaseModel):
    query: str = ""
    property_id: Optional[str] = None
    refresh: bool = False


class CaptureRequest(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    property_id: Optional[str] = None
    address: Optional[str] = None


class NightlyRequest(BaseModel):
    date: Optional[str] = None


class LearnRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=120)
    job_type: Optional[str] = None
    property_id: Optional[str] = None


class AttachRequest(BaseModel):
    property_id: Optional[str] = None
    job_type: Optional[str] = None
    detach: bool = False


class ReviewRequest(BaseModel):
    action: str
    payload: Optional[dict[str, Any]] = None
    note: str = ""


# ----------------------------------------------------------------- nightly scheduler
_auto_ran_on: str | None = None  # survives demo resets, so a reset never re-triggers the nightly pass


async def _nightly_loop() -> None:
    """Runs the nightly route pass once a day at SITE_MEMORY_NIGHTLY_AT (local time)."""
    global _auto_ran_on
    while True:
        try:
            s = get_settings()
            at = s["nightly_at"]
            if at.lower() != "off":
                now = datetime.now()
                today = date.today().isoformat()
                store = get_store()
                if now.strftime("%H:%M") >= at and store.session().get("nightly_auto_on") != today and _auto_ran_on != today:
                    _auto_ran_on = today
                    await agent.nightly(store)
                    store.touch_session(nightly_auto_on=today)
        except Exception as exc:  # never kill the server over the scheduler
            with contextlib.suppress(Exception):
                get_store().log("nightly_error", str(exc)[:200])
        await asyncio.sleep(60)


async def _demo_reset_loop() -> None:
    """Public demo only: restore the MN Labs sample memory on a schedule."""
    while True:
        await asyncio.sleep(30)
        try:
            if demo.clock.due():
                get_store().reset_to_seed()
                demo.clock.mark()
                get_store().log("demo_reset", "Scheduled reset of the public demo data")
        except Exception as exc:
            with contextlib.suppress(Exception):
                get_store().log("demo_reset_error", str(exc)[:200])


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks = []
    if get_settings()["nightly_at"].lower() != "off":
        tasks.append(asyncio.create_task(_nightly_loop()))
    if demo.enabled():
        demo.clock.mark()
        tasks.append(asyncio.create_task(_demo_reset_loop()))
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="Site Memory", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def demo_guard(request: Request, call_next):
    """Rate limits for the shared public demo (no-op on a local install)."""
    if demo.enabled() and request.url.path.startswith("/api/"):
        ip = demo.client_ip(request.headers, request.client.host if request.client else None)
        ok, msg, retry = demo.limiter.check(ip, request.method, request.url.path)
        if not ok:
            return JSONResponse({"detail": msg}, status_code=429, headers={"Retry-After": str(retry)})
    return await call_next(request)


def _404(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Not found: {what}")


# ----------------------------------------------------------------- status
@app.get("/api/status")
def status():
    s = get_settings()
    store = get_store()
    return {
        "app": "Site Memory", "version": __version__, "business": BUSINESS_NAME,
        "mode": "dry-run" if s["dry_run"] else "nemotron-live",
        "provider": "local heuristics" if s["dry_run"] else "Nebius Token Factory",
        "model": s["model"], "nightly_model": s["nightly_model"], "skills_model": s["skills_model"], "nightly_at": s["nightly_at"],
        "stats": store.stats(), "last_llm": store.last_llm(), "session": store.session(),
        "demo": demo.status(), "lookup": lookup.enabled(),
    }


# ----------------------------------------------------------------- properties + brief
@app.get("/api/properties")
def properties():
    return {"properties": get_store().list_properties()}


@app.get("/api/properties/{pid}")
def property_detail(pid: str):
    b = get_store().property_bundle(pid)
    if b is None:
        raise _404(pid)
    return b


@app.post("/api/arrive")
async def arrive(req: ArriveRequest):
    return await agent.arrival_brief(get_store(), req.query, property_id=req.property_id, refresh=req.refresh)


@app.post("/api/capture")
async def capture(req: CaptureRequest):
    return await agent.capture(get_store(), req.text, property_id=req.property_id, address=req.address)


class PreviewRequest(BaseModel):
    text: str = ""


@app.post("/api/capture/preview")
def capture_preview(req: PreviewRequest):
    """Local only (no AI): which codes would be split into the vault, and which property it looks like."""
    from site_memory.redact import split_secrets

    redacted, secrets = split_secrets(req.text or "")
    prop, _ = get_store().resolve_property(req.text or "")
    return {"redacted": redacted, "secrets": [s["label"] for s in secrets], "property": prop}


@app.post("/api/facts/{fid}/forget")
def forget_fact(fid: str):
    f = get_store().forget_fact(fid)
    if f is None:
        raise _404(fid)
    return {"fact": f}


@app.post("/api/facts/{fid}/redact")
def redact_fact(fid: str):
    f = get_store().redact_fact(fid)
    if f is None:
        raise _404(fid)
    return {"fact": f}


@app.post("/api/facts/{fid}/lookup")
async def lookup_fact(fid: str):
    """Manual + firmware lookup (Tavily search, Nemotron summary). Sends make/model only."""
    store = get_store()
    f = store.get_fact(fid)
    if f is None:
        raise _404(fid)
    if not lookup.enabled():
        raise HTTPException(status_code=400, detail="Manual lookup is off: set TAVILY_API_KEY to enable it.")
    res = await lookup.lookup(f, store.vault.plaintexts())
    meta = res.pop("meta", None)
    if meta:
        store.log_llm(meta)
    if res.get("ok") and not res.get("cached"):
        store.log("lookup", f"Manual lookup for {f['label']}: \"{res['query']}\" ({len(res['results'])} results)", fact_id=fid)
    return {**res, "source": (meta or {}).get("source"), "model": (meta or {}).get("model")}


@app.post("/api/notes/{nid}/forget")
def forget_note(nid: str):
    n = get_store().forget_note(nid)
    if n is None:
        raise _404(nid)
    return {"note": n}


@app.get("/api/vault")
def vault(property_id: Optional[str] = None):
    return {"secrets": get_store().vault.list(property_id)}


@app.post("/api/vault/{sid}/reveal")
def vault_reveal(sid: str):
    store = get_store()
    value = store.vault.reveal(sid)
    if value is None:
        raise _404(sid)
    store.log("vault_reveal", f"Revealed {sid} on this device (never sent to the AI)", secret_id=sid)
    return {"id": sid, "value": value}


# ----------------------------------------------------------------- route / nightly
@app.get("/api/route")
def route(date: Optional[str] = None):
    store = get_store()
    r = store.route(date)
    n = store.nightly()
    return {"route": r, "nightly": n if n and n.get("for_date") == r["date"] else None}


@app.post("/api/route/nightly")
async def route_nightly(req: Optional[NightlyRequest] = None):
    return await agent.nightly(get_store(), req.date if req else None)


# ----------------------------------------------------------------- skills
@app.get("/api/skills")
def skills():
    return {"skills": get_store().skills()}


@app.get("/api/skills/{sid}")
def skill(sid: str):
    store = get_store()
    s = store.get_skill(sid)
    if not s:
        raise _404(sid)
    diffs = []
    for prev, cur in zip(s["versions"], s["versions"][1:]):
        diffs.append({"from": prev["version"], "to": cur["version"], "lines": skillfiles.diff_lines(prev["body_md"], cur["body_md"])})
    return {"skill": s, "diffs": diffs, "file": str(store.skills_dir / f"{s['slug']}.md")}


@app.get("/api/skills/{sid}/checklist", response_class=PlainTextResponse)
def skill_checklist(sid: str, property_id: Optional[str] = None):
    store = get_store()
    s = store.get_skill(sid)
    if not s:
        raise _404(sid)
    bundle = store.property_bundle(property_id) if property_id else None
    store.log("exported", f"Checklist: {s['title']} v{s['version']}" + (f" for {bundle['property']['address']}" if bundle else ""), skill_id=s["id"])
    return skillfiles.export_checklist(s, bundle, BUSINESS_NAME)


@app.post("/api/skills/learn")
async def skills_learn(req: LearnRequest):
    return await agent.learn_skill(get_store(), req.topic, job_type=req.job_type, property_id=req.property_id)


@app.post("/api/skills/{sid}/improve")
async def skills_improve(sid: str):
    try:
        return await agent.improve_skill(get_store(), sid)
    except KeyError:
        raise _404(sid)


@app.post("/api/skills/{sid}/attach")
def skills_attach(sid: str, req: AttachRequest):
    s = get_store().attach_skill(sid, property_id=req.property_id, job_type=req.job_type, detach=req.detach)
    if not s:
        raise _404(sid)
    return {"skill": s}


# ----------------------------------------------------------------- review gate
def _review_view(pr: dict) -> dict:
    store = get_store()
    out = agent._public_proposal(pr)
    if pr["kind"] == "skill_update":
        sk = store.get_skill(pr["payload"].get("skill_id", ""))
        base = sk["versions"][-1]["body_md"] if sk else ""
        if sk and pr["status"] in ("approved", "edited"):
            match = [v for v in sk["versions"] if v.get("proposal_id") == pr["id"]]
            prev = [v for v in sk["versions"] if match and v["version"] == match[0]["version"] - 1]
            base = prev[0]["body_md"] if prev else base
        out["diff"] = skillfiles.diff_lines(base, pr["payload"].get("body_md", ""))
        out["skill_title"] = sk["title"] if sk else ""
    if pr["kind"] == "memory":
        pid = pr["payload"].get("property_id")
        p = store.get_property(pid) if pid else None
        out["property"] = p
    return out


@app.get("/api/review")
def review(status: str = "pending,later"):
    return {"proposals": [_review_view(p) for p in get_store().proposals(status)]}


@app.get("/api/review/{prid}")
def review_one(prid: str):
    pr = get_store().get_proposal(prid)
    if not pr:
        raise _404(prid)
    return {"proposal": _review_view(pr)}


@app.post("/api/review/{prid}")
def review_decide(prid: str, req: ReviewRequest):
    store = get_store()
    pr = store.get_proposal(prid)
    if not pr:
        raise _404(prid)
    payload = req.payload
    if payload is not None and pr["kind"] == "memory":
        # sealed secrets never travel to the browser, so keep the originals
        payload = {**payload, "sealed_secrets": pr["payload"].get("sealed_secrets", [])}
    try:
        res = store.decide(prid, req.action, payload=payload, note=req.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    res["proposal"] = _review_view(res["proposal"])
    return res


# ----------------------------------------------------------------- journal + demo
@app.get("/api/journal")
def journal(limit: int = 60):
    return {"journal": get_store().journal(limit)}


@app.post("/api/demo/reset")
def demo_reset():
    store = get_store()
    store.reset_to_seed()
    if demo.enabled():
        demo.clock.mark()
    return {"ok": True, "stats": store.stats()}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
