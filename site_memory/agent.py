"""Site Memory tasks: capture -> proposal, arrival brief, nightly route pass,
learn / improve skills. Each task calls Nemotron via Token Factory and falls back
to local heuristics when no key is set. Nothing here writes to memory or skills
directly: captures and skills become proposals for the human gate.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from site_memory import dry_run
from site_memory.config import BUSINESS_NAME, get_settings
from site_memory.memory import MemoryStore
from site_memory.nebius_client import chat_json
from site_memory.redact import PLACEHOLDER_RE, split_secrets

VOICE = (
    f"You work for {BUSINESS_NAME}, a one-person UK installer (CCTV, alarms, smart home, "
    "heating and electrical). UK English, short and practical, written for a tradesperson "
    "reading a phone on a doorstep. Never invent facts. Never reveal or guess codes, PINs or "
    "passwords: anything shown as [vault: ...] is in an encrypted vault; say 'code in vault'."
)

CAPTURE_SYSTEM = VOICE + """
Turn the installer's quick site note into structured property memory.
Return JSON only:
{"address": "street address if the note names one, else empty",
 "town": "", "postcode": "", "customer": "",
 "summary": "one line: what this note adds",
 "facts": [{"kind": "asset|access|cable|customer|warranty|service|general",
            "label": "short noun, e.g. NVR, Front camera, Boiler, Parking, Dog",
            "value": "the fact in a few words",
            "make": "", "model": "", "location": "",
            "installed": "YYYY-MM-DD or empty", "warranty_until": "YYYY-MM-DD or empty",
            "service_due": "YYYY-MM-DD or empty"}]}
Rules: dates in notes are UK format (12/10/2026 means 12 October 2026); one fact per asset or instruction; reuse a label from known_labels ONLY for the very
same physical item (e.g. the same NVR moved), otherwise give a new specific label (a newly fitted camera
is "Back door camera", not an existing label); dates only if stated (today is given); max 10 facts;
never put a [vault: ...] placeholder or any code into a fact."""

BRIEF_SYSTEM = VOICE + """
Write an arrival brief for the installer standing at this property. Use ONLY the facts, notes and
flags provided. Every bullet must cite the note id(s) it came from, using ids exactly as given
(e.g. "n-0004"). Lead with anything that could bite (dog, access, conflicts, stale info), then the
customer, the kit, and anything due. Include one bullet for every item in "flags" (conflicts, stale
facts, due dates). If two notes conflict, say so and say which is newer. Do not add anything that is
not written in the notes or facts: no assumptions, no generic safety advice.
Return JSON only:
{"headline": "one line, max 14 words",
 "bullets": [{"tag": "access|customer|kit|risk|due|job", "text": "max 28 words", "cites": ["n-0001"]}]}
3 to 6 bullets."""

NIGHTLY_SYSTEM = VOICE + """
It is the evening before a working day. Write tomorrow's route briefing from the jobs, property facts,
attached skills and due items provided. For each job give 2-4 prep points the installer should know
before setting off, citing note ids exactly as given, and what to bring (kit or skill checklist titles).
Then list warranty / service items falling due, and say which are not booked yet.
Return JSON only:
{"headline": "one line",
 "jobs": [{"job_id": "j-01", "prep": [{"text": "max 24 words", "cites": ["n-0001"]}], "bring": ["short item"]}],
 "due_actions": [{"text": "max 24 words"}]}"""

LEARN_SYSTEM = VOICE + """
You are the installer's apprentice. From their own site notes and past edits, write ONE reusable skill:
a markdown checklist another installer, sub or apprentice could follow. Capture how THIS installer does
it (their kit choices, their order of work, their lessons learned), not generic advice.
Return JSON only:
{"title": "e.g. How I commission a Dahua NVR",
 "summary": "one line",
 "job_types": ["kebab-case job type"],
 "learned_from": ["note ids you actually used"],
 "body_md": "# Title\\n\\n## Section\\n- [ ] step\\n..."}
8 to 16 checklist steps, grouped under 2-4 headings. No codes or passwords."""

IMPROVE_SYSTEM = VOICE + """
You maintain the installer's skill files. Propose the next version of this skill.
Only make changes that are grounded in (a) a note marked "new_since_this_version": true, or (b) the
installer's own past edits (what they added or removed is a strong signal of how they work). Do not
re-add steps the skill already covers, do not pad, keep their wording where it still fits, and keep the
markdown checklist form. If nothing new is worth adding, return "changes": [] and the body unchanged.
Return JSON only:
{"changes": [{"change": "what you added / changed", "because": "n-0000 or 'your edit'"}],
 "body_md": "full new markdown", "change_note": "one line: what changed and why",
 "learned_from": ["note ids used"]}"""


def _today() -> str:
    return date.today().isoformat()


def _valid_cites(cites: Any, allowed: set[str]) -> list[str]:
    if isinstance(cites, str):
        cites = re.findall(r"n-\d{4}", cites)
    out = []
    for c in cites or []:
        c = str(c).strip().strip("[]").lower()
        if c in allowed and c not in out:
            out.append(c)
    return out


_SUPPORT_STOP = {"with", "from", "that", "this", "have", "been", "into", "their", "there", "they", "your", "will",
                 "should", "check", "note", "notes", "says", "said", "site", "keep", "make", "sure", "before", "after",
                 "also", "only", "then", "when", "what", "where", "which", "about", "confirm", "newer", "older", "newest",
                 "installed", "fitted", "located", "near", "next", "left", "right", "needs", "need", "may", "might"}


def _support_corpus(store: MemoryStore, cites: list[str]) -> str:
    parts = []
    for nid in cites:
        n = store.get_note(nid)
        if n:
            parts.append(n["text"])
    for f in store.facts():
        if f["note_id"] in cites:
            parts += [f.get(k, "") for k in ("label", "value", "make", "model", "location")]
            for k in ("installed", "warranty_until", "service_due", "recorded_at"):
                if f.get(k):
                    d = date.fromisoformat(f[k][:10])
                    parts += [f[k], d.strftime("%B %Y %b"), "due", "warranty", "service", "ends"]
    for fl in store.flags():
        if set(fl["note_ids"]) & set(cites):
            parts.append(fl["message"] + " conflict stale")
    return " ".join(parts).lower()


def supported(store: MemoryStore, text: str, cites: list[str], threshold: float = 0.5) -> bool:
    """Cheap grounding check: most content words in a bullet must appear in the cited notes."""
    corpus = _support_corpus(store, cites)
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3 and w not in _SUPPORT_STOP]
    if not words:
        return True
    hits = sum(1 for w in words if w in corpus or (w.endswith("s") and w[:-1] in corpus))
    return hits / len(words) >= threshold


def _same(a: str, b: str) -> bool:
    wa, wb = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
    return bool(wa and wb) and len(wa & wb) / max(1, min(len(wa), len(wb))) > 0.8


def _clean_text(s: Any) -> str:
    return re.sub(r"\s*\[?n-\d{4}\]?", "", str(s or "")).strip()


# --------------------------------------------------------------------------- capture
async def capture(store: MemoryStore, text: str, *, property_id: str | None = None, address: str | None = None) -> dict:
    """Quick capture -> proposal waiting for approval. Secrets are split out and sealed first."""
    redacted, secrets = split_secrets(text.strip())
    prop = store.get_property(property_id) if property_id else None
    if prop is None:
        prop, _ = store.resolve_property(address or redacted)
    known = sorted({f["label"] for f in store.facts(prop["id"])}) if prop else []
    payload = {"today": _today(), "note": redacted,
               "property": ({k: prop[k] for k in ("address", "town", "postcode", "customer")} if prop else None),
               "known_labels": known}
    parsed, meta = await chat_json("capture", CAPTURE_SYSTEM, payload, max_tokens=900, forbidden=store.vault.plaintexts())
    store.log_llm(meta)
    result = parsed if isinstance(parsed, dict) else dry_run.extract_capture(redacted)
    facts = []
    for f in (result.get("facts") or [])[:12]:
        if not isinstance(f, dict):
            continue
        clean = {k: str(f.get(k) or "").strip() for k in ("kind", "label", "value", "make", "model", "location", "installed", "warranty_until", "service_due")}
        for k in ("value", "label", "make", "model", "location"):
            clean[k] = PLACEHOLDER_RE.sub("", split_secrets(clean[k])[0]).strip(" ,.")
        if clean["value"] or clean["model"]:
            facts.append(clean)
    _fix_uk_dates(facts, redacted)
    new_property = None
    if prop is None:
        addr = (result.get("address") or address or "").strip()
        new_property = {"address": addr or "New property (edit address)", "town": result.get("town", ""),
                        "postcode": result.get("postcode", ""), "customer": result.get("customer", "")}
    where = prop["address"] if prop else (new_property or {}).get("address", "new property")
    sealed = [{"label": s["label"], "token": store.vault.seal(s["value"])} for s in secrets]
    pr = store.add_proposal(
        "memory",
        f"Save to {where}: {len(facts)} fact{'s' if len(facts) != 1 else ''}" + (f" + {len(sealed)} code(s) to vault" if sealed else ""),
        str(result.get("summary") or "")[:200],
        {"property_id": prop["id"] if prop else None, "new_property": new_property, "note_text": redacted,
         "facts": facts, "sealed_secrets": sealed, "secret_labels": [s["label"] for s in secrets]},
        source=meta["source"], model=meta["model"],
    )
    return {"proposal": _public_proposal(pr), "llm": meta, "secrets_found": [s["label"] for s in secrets]}


def _fix_uk_dates(facts: list[dict], note: str) -> None:
    """Models sometimes read 12/10/2026 as 10 December. Re-anchor any date that is a
    day/month swap of a dd/mm/yyyy date actually written in the note."""
    uk = []
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", note):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        try:
            uk.append(date(y, mo, d))
        except ValueError:
            pass
    for f in facts:
        for k in ("installed", "warranty_until", "service_due"):
            try:
                got = date.fromisoformat(f.get(k, "")[:10])
            except ValueError:
                continue
            for u in uk:
                if got != u and got.year == u.year and got.month == u.day and got.day == u.month:
                    f[k] = u.isoformat()


def _public_proposal(pr: dict) -> dict:
    """Strip sealed tokens before anything goes to the browser."""
    out = {**pr, "payload": {k: v for k, v in pr["payload"].items() if k != "sealed_secrets"}}
    if "final_payload" in out:
        out["final_payload"] = {k: v for k, v in out["final_payload"].items() if k != "sealed_secrets"}
    return out


# --------------------------------------------------------------------------- arrival brief
async def arrival_brief(store: MemoryStore, query: str = "", *, property_id: str | None = None, refresh: bool = False) -> dict:
    prop = store.get_property(property_id) if property_id else None
    candidates: list[dict] = []
    if prop is None:
        prop, candidates = store.resolve_property(query)
    if prop is None:
        return {"resolved": False, "query": query, "candidates": candidates,
                "message": "I don't have that address yet. Pick one below or capture a first note."}
    pid = prop["id"]
    bundle = store.property_bundle(pid)
    ctx = store.llm_property_context(pid)
    allowed = {n["id"] for n in bundle["notes"]}
    cached = None if refresh else store.cached_brief(pid)
    if cached:
        summary = cached
    else:
        parsed, meta = await chat_json("arrival_brief", BRIEF_SYSTEM, {"today": _today(), **ctx}, max_tokens=800,
                                       forbidden=store.vault.plaintexts())
        store.log_llm(meta)
        raw = parsed if isinstance(parsed, dict) and parsed.get("bullets") else dry_run.arrival_bullets(ctx)
        bullets, dropped = [], 0
        for b in raw.get("bullets", [])[:8]:
            if not isinstance(b, dict):
                continue
            cites = _valid_cites(b.get("cites"), allowed)
            text = _clean_text(b.get("text"))
            if not cites or not text or not supported(store, text, cites):
                dropped += 1       # uncited or unsupported claims never reach the installer
                continue
            if any(_same(text, b2["text"]) for b2 in bullets):
                continue
            bullets.append({"tag": b.get("tag") or "kit", "text": split_secrets(text)[0], "cites": cites})
        cited = {c for b in bullets for c in b["cites"]}
        for fl in bundle["flags"]:
            if not set(fl["note_ids"]) & cited:   # every conflict / stale / due flag must surface
                bullets.append({"tag": "risk" if fl["type"] in ("conflict", "stale") else "due", "text": fl["message"],
                                "cites": [c for c in fl["note_ids"] if c in allowed][:2], "from_rules": True})
                cited |= set(fl["note_ids"])
        summary = {"headline": _clean_text(raw.get("headline")) or prop["address"], "bullets": bullets, "dropped_uncited": dropped,
                   "source": meta["source"] if parsed else ("dry-run" if meta["source"] == "dry-run" else "dry-run-fallback"),
                   "model": meta["model"], "latency_ms": meta.get("latency_ms"),
                   "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        store.cache_brief(pid, summary)
    store.touch_session(last_property_id=pid, last_question=query or prop["address"])
    facts = bundle["facts"]
    sections = {k: [f for f in facts if f["kind"] == k] for k in ("customer", "access", "asset", "cable", "general", "warranty", "service")}
    return {"resolved": True, "query": query, "property": prop, "summary": summary, "sections": sections,
            "flags": bundle["flags"], "secrets": bundle["secrets"], "skills": bundle["skills"], "jobs": bundle["jobs"],
            "notes": {n["id"]: {"date": n["recorded_at"], "text": n["text"]} for n in bundle["notes"]}, "cached": bool(cached)}


# --------------------------------------------------------------------------- nightly
async def nightly(store: MemoryStore, day: str | None = None) -> dict:
    route = store.route(day)
    s = get_settings()
    ctx_jobs = []
    for it in route["jobs"]:
        j, p = it["job"], it["property"]
        ctx_jobs.append({
            "job_id": j["id"], "time": j["time"], "job_type": j["job_type"], "title": j["title"],
            "address": f"{p.get('address')}, {p.get('town')} {p.get('postcode')}", "customer": p.get("customer"),
            "access": [{"value": f["value"], "note_id": f["note_id"]} for f in it["access"]],
            "kit": [{"label": f["label"], "value": f["value"], "location": f.get("location"), "note_id": f["note_id"]} for f in it["kit"]],
            "flags": [{"message": f["message"], "note_ids": f["note_ids"]} for f in it["flags"]],
            "skills": [{"title": sk["title"], "version": sk["version"]} for sk in it["skills"]],
            "vault_items": it["vault_count"],
        })
    ctx = {"today": _today(), "route_date": route["date"], "jobs": ctx_jobs,
           "due": [{"message": d["message"], "address": d["address"], "booked": d["booked"]} for d in route["due"]]}
    parsed, meta = await chat_json("nightly", NIGHTLY_SYSTEM, ctx, model=s["nightly_model"], max_tokens=1400,
                                   forbidden=store.vault.plaintexts())
    store.log_llm(meta)
    raw = parsed if isinstance(parsed, dict) and parsed.get("jobs") is not None else dry_run.nightly(
        {"jobs": [{**c, "access": it["access"], "flags": it["flags"], "skills": it["skills"]} for c, it in zip(ctx_jobs, route["jobs"])],
         "due": route["due"]})
    by_job = {}
    for it in route["jobs"]:
        allowed = {f["note_id"] for f in store.facts(it["job"]["property_id"])}
        by_job[it["job"]["id"]] = allowed
    jobs_out = []
    for jb in raw.get("jobs", []):
        jid = jb.get("job_id")
        if jid not in by_job:
            continue
        prep = []
        for pnt in jb.get("prep", [])[:5]:
            txt = _clean_text(pnt.get("text") if isinstance(pnt, dict) else pnt)
            cites = _valid_cites(pnt.get("cites") if isinstance(pnt, dict) else [], by_job[jid])
            if txt:
                prep.append({"text": split_secrets(txt)[0], "cites": cites})
        jobs_out.append({"job_id": jid, "prep": prep, "bring": [str(b)[:60] for b in jb.get("bring", [])][:5]})
    result = {"for_date": route["date"], "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "headline": _clean_text(raw.get("headline")) or f"Route for {route['date']}",
              "jobs": jobs_out, "due_actions": [{"text": _clean_text(d.get("text") if isinstance(d, dict) else d)} for d in raw.get("due_actions", [])][:8],
              "source": meta["source"] if parsed else ("dry-run" if meta["source"] == "dry-run" else "dry-run-fallback"),
              "model": meta["model"], "latency_ms": meta.get("latency_ms")}
    store.set_nightly(result)
    store.log("nightly", f"Route briefing for {route['date']} ({result['source']}, {meta['model']})")
    return {"route": route, "nightly": result}


# --------------------------------------------------------------------------- skills
def _skill_notes(store: MemoryStore, topic: str, job_type: str | None, property_id: str | None) -> list[dict]:
    notes: dict[str, dict] = {}
    if property_id:
        for n in store.notes(property_id):
            notes[n["id"]] = n
    if job_type:
        pids = {j["property_id"] for j in store.jobs() if j["job_type"] == job_type}
        for pid in pids:
            for n in store.notes(pid):
                notes.setdefault(n["id"], n)
    for n in store.search(topic, limit=8):
        notes.setdefault(n["id"], n)
    return list(notes.values())[:12]


async def learn_skill(store: MemoryStore, topic: str, *, job_type: str | None = None, property_id: str | None = None) -> dict:
    notes = _skill_notes(store, topic, job_type, property_id)
    ctx = {"topic": topic, "job_type": job_type,
           "notes": [{"id": n["id"], "date": n["recorded_at"], "text": n["text"]} for n in notes],
           "your_past_edits": store.edit_signals(limit=6),
           "existing_skills": [s["title"] for s in store.skills()]}
    parsed, meta = await chat_json("learn_skill", LEARN_SYSTEM, ctx, model=get_settings()["skills_model"], max_tokens=1600,
                                   forbidden=store.vault.plaintexts())
    store.log_llm(meta)
    raw = parsed if isinstance(parsed, dict) and parsed.get("body_md") else dry_run.learn_skill(topic, notes, job_type)
    allowed = {n["id"] for n in notes}
    payload = {"title": str(raw.get("title") or topic)[:80], "summary": str(raw.get("summary") or "")[:200],
               "job_types": [str(j) for j in (raw.get("job_types") or ([job_type] if job_type else []))][:3],
               "learned_from": _valid_cites(raw.get("learned_from"), allowed),
               "property_ids": [property_id] if property_id else [],
               "body_md": split_secrets(str(raw.get("body_md") or ""))[0]}
    pr = store.add_proposal("skill_new", f"New skill: {payload['title']}", payload["summary"], payload,
                            source=meta["source"] if parsed else meta["source"], model=meta["model"])
    return {"proposal": _public_proposal(pr), "llm": meta}


async def improve_skill(store: MemoryStore, skill_id: str) -> dict:
    sk = store.get_skill(skill_id)
    if not sk:
        raise KeyError(skill_id)
    notes: dict[str, dict] = {}
    for pid in sk.get("property_ids", []):
        for n in store.notes(pid):
            notes[n["id"]] = n
    for jt in sk.get("job_types", []):
        for n in _skill_notes(store, sk["title"], jt, None):
            notes.setdefault(n["id"], n)
    for n in store.search(sk["title"] + " " + " ".join(sk.get("job_types", [])).replace("-", " "), limit=6):
        notes.setdefault(n["id"], n)
    since = sk.get("updated_at") or ""
    recent = sorted(notes.values(), key=lambda n: (n["recorded_at"] > since, n["recorded_at"]), reverse=True)[:8]
    ctx = {"skill": {"title": sk["title"], "version": sk["version"], "last_updated": since, "body_md": sk["body_md"],
                     "history": [{"version": v["version"], "change_note": v["change_note"]} for v in sk["versions"]]},
           "recent_notes": [{"id": n["id"], "date": n["recorded_at"], "new_since_this_version": n["recorded_at"] > since,
                             "text": n["text"]} for n in recent],
           "your_past_edits": store.edit_signals(sk["id"], limit=6)}
    parsed, meta = await chat_json("improve_skill", IMPROVE_SYSTEM, ctx, model=get_settings()["skills_model"], max_tokens=1600,
                                   forbidden=store.vault.plaintexts())
    store.log_llm(meta)
    raw = parsed if isinstance(parsed, dict) and parsed.get("body_md") else dry_run.improve_skill(sk, recent, store.edit_signals(sk["id"]))
    from site_memory.skills import normalise

    if normalise(str(raw.get("body_md") or "")) == normalise(sk["body_md"]):
        return {"proposal": None, "no_change": True, "llm": meta,
                "message": f"Nothing new to learn since v{sk['version']}. Capture more notes or edit the skill."}
    from site_memory.skills import edit_signal

    new_body = split_secrets(str(raw["body_md"]))[0]
    sig = edit_signal(sk["body_md"], new_body)
    touched = " ".join(sig["added"] + sig["removed"]).lower()
    changes = []
    for c in (raw.get("changes") or []):
        if not isinstance(c, dict):
            continue
        words = [w for w in re.findall(r"[a-z0-9]+", str(c.get("change", "")).lower()) if len(w) > 3 and w not in _SUPPORT_STOP
                 and w not in {"added", "step", "reminder", "note", "item", "removed", "changed", "updated", "clarified"}]
        if words and sum(w in touched for w in words) / len(words) >= 0.4:   # only claims the diff backs up
            changes.append({"change": str(c.get("change"))[:200], "because": str(c.get("because", ""))[:20]})
    payload = {"skill_id": sk["id"], "from_version": sk["version"], "body_md": new_body,
               "changes": changes[:8],
               "change_note": str(raw.get("change_note") or "Improved")[:200],
               "learned_from": _valid_cites(raw.get("learned_from"), {n["id"] for n in recent})}
    pr = store.add_proposal("skill_update", f"{sk['title']}: v{sk['version']} → v{sk['version'] + 1}", payload["change_note"], payload,
                            source=meta["source"], model=meta["model"])
    return {"proposal": _public_proposal(pr), "llm": meta}
