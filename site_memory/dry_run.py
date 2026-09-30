"""Local heuristics used when no Nebius key is set (or Token Factory is unreachable).

Same outputs as the Nemotron paths, so the UI and the approval gate behave the same.
"""

from __future__ import annotations

import re
from datetime import date

BRANDS = ["hikvision", "dahua", "texecom", "pyronix", "ajax", "worcester bosch", "worcester", "ideal", "vaillant", "baxi",
          "hager", "wylex", "schneider", "aico", "nest", "reolink", "ring", "hive", "ubiquiti", "unifi", "bt", "uniview", "eufy"]
ASSET_WORDS = [("nvr", "NVR"), ("dvr", "DVR"), ("consumer unit", "Consumer unit"), ("fuse board", "Consumer unit"),
               ("boiler", "Boiler"), ("combi", "Boiler"), ("thermostat", "Thermostat"), ("doorbell", "Video doorbell"),
               ("panel", "Alarm panel"), ("hub", "Hub"), ("router", "Router / ONT"), ("ont", "Router / ONT"),
               ("switch", "Network switch"), ("pir", "Detectors"), ("detector", "Detectors"), ("smoke", "Smoke / heat alarms"),
               ("camera", "Camera"), ("cam", "Camera"), ("turret", "Camera"), ("bullet", "Camera"), ("dome", "Camera"),
               ("ev charger", "EV charger"), ("solar", "Solar inverter"), ("inverter", "Solar inverter")]
ACCESS_WORDS = ["dog", "park", "permit", "key", "gate", "access", "notice", "ring ", "knock", "tea", "elderly", "shutter", "ladder", "loft"]
CABLE_WORDS = ["cable", "cat6", "cat5", "route", "trunking", "duct", "soffit", "conduit", "clipped", "fibre"]
CUSTOMER_WORDS = ["customer", "owner", "landlord", "tenant", "prefers", "wfh", "work from home"]
LOC_RE = re.compile(r"\b(?:in|on|above|under|behind|next to|by|at)\s+(?:the\s+)?([a-z0-9' -]{3,40}?)(?:[.,;]|$| and | with )", re.I)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})|(\d{1,2})/(\d{1,2})/(\d{2,4})")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(s.strip()) > 3]


def _date_in(s: str) -> str:
    m = DATE_RE.search(s)
    if not m:
        return ""
    if m.group(1):
        return m.group(1)
    d, mo, y = int(m.group(2)), int(m.group(3)), int(m.group(4))
    y = y + 2000 if y < 100 else y
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return ""


def extract_capture(text: str) -> dict:
    facts = []
    for s in _sentences(text):
        low = s.lower()
        if "[vault:" in low and len(re.sub(r"\[vault:[^\]]+\]", "", low).strip(" .,")) < 12:
            continue
        brand = next((b for b in BRANDS if re.search(rf"\b{re.escape(b)}\b", low)), "")
        asset = next((lab for w, lab in ASSET_WORDS if re.search(rf"\b{re.escape(w)}s?\b", low)), "")
        loc = LOC_RE.search(s)
        f = {"kind": "general", "label": "Note", "value": s[:160], "make": "", "model": "", "location": "",
             "installed": "", "warranty_until": "", "service_due": ""}
        if asset or brand:
            f["kind"], f["label"] = "asset", asset or brand.title()
            f["make"] = brand.title() if brand else ""
            if brand:
                after = s[low.index(brand) + len(brand):].split()
                model = next((w.strip(",.") for w in after[:4] if re.search(r"\d", w)), "")
                f["model"] = model
            f["location"] = loc.group(1).strip() if loc else ""
            f["value"] = (f"{f['make']} {f['model']}".strip() or s[:80])
        elif any(w in low for w in CABLE_WORDS):
            f["kind"], f["label"] = "cable", "Cable route"
        elif any(w in low for w in CUSTOMER_WORDS) or re.search(r"\b0\d{3,4}\s?\d{3}\s?\d{3,4}\b", s):
            f["kind"], f["label"] = "customer", "Customer"
        elif any(w in low for w in ACCESS_WORDS):
            f["kind"], f["label"] = "access", "Access"
        dt = _date_in(s)
        if dt:
            if "warrant" in low or "guarantee" in low:
                f["warranty_until"] = dt
            elif "service" in low or "due" in low:
                f["service_due"] = dt
        facts.append(f)
    return {"summary": f"{len(facts)} fact(s) pulled out by local heuristics (no Nemotron).", "facts": facts[:12]}


def arrival_bullets(ctx: dict) -> dict:
    facts = ctx.get("facts", [])
    bullets = []

    def add(tag: str, text: str, cites: list[str]) -> None:
        bullets.append({"tag": tag, "text": text, "cites": [c for c in cites if c]})

    for f in facts:
        if f["kind"] == "customer":
            add("customer", f["value"], [f["note_id"]])
            break
    for f in [f for f in facts if f["kind"] == "access"][:2]:
        add("access", f["value"], [f["note_id"]])
    for fl in ctx.get("flags", [])[:3]:
        add("risk" if fl["type"] in ("conflict", "stale") else "due", fl["message"], fl["note_ids"][:2])
    kit = [f for f in facts if f["kind"] == "asset"][:3]
    if kit:
        add("kit", "Kit on site: " + "; ".join(f"{f['label']} ({f.get('location') or 'location not noted'})" for f in kit), [f["note_id"] for f in kit])
    head = f"{ctx['property']['address']}: {len([f for f in facts if f['kind'] == 'asset'])} assets on record"
    return {"headline": head, "bullets": bullets[:6]}


def nightly(route_ctx: dict) -> dict:
    jobs = []
    for j in route_ctx.get("jobs", []):
        prep = [{"text": a["value"], "cites": [a["note_id"]]} for a in j.get("access", [])[:2]]
        for fl in j.get("flags", [])[:2]:
            prep.append({"text": fl["message"], "cites": fl["note_ids"][:1]})
        jobs.append({"job_id": j["job_id"], "prep": prep, "bring": [s["title"] for s in j.get("skills", [])][:2]})
    due = [{"text": d["message"] + (" (booked)" if d.get("booked") else " (not booked yet)")} for d in route_ctx.get("due", [])]
    n = len(jobs)
    return {"headline": f"{n} job{'s' if n != 1 else ''} tomorrow, {len(due)} warranty/service item(s) due in 30 days.", "jobs": jobs, "due_actions": due}


def learn_skill(topic: str, notes: list[dict], job_type: str | None) -> dict:
    lines = [f"# {topic.strip().capitalize()}", ""]
    used = []
    for n in notes[:6]:
        for s in _sentences(n["text"])[:2]:
            if "[vault:" in s:
                continue
            lines.append(f"- [ ] {s.rstrip('.')}")
            used.append(n["id"])
    lines.append("- [ ] Record what you did in Site Memory before leaving")
    return {"title": topic.strip().capitalize(), "summary": f"Draft checklist from {len(set(used))} note(s), local heuristics.",
            "job_types": [job_type] if job_type else [], "learned_from": sorted(set(used)), "body_md": "\n".join(lines) + "\n"}


def improve_skill(skill: dict, notes: list[dict], signals: list[dict]) -> dict:
    body = skill["body_md"].rstrip("\n")
    added = []
    for sig in signals[-3:]:
        for a in sig.get("added", [])[:2]:
            if a not in body:
                added.append(a if a.startswith("- [") else f"- [ ] {a.lstrip('- ')}")
    since = skill.get("updated_at") or ""
    for n in [n for n in notes if n.get("recorded_at", "") > since][:2]:
        s = _sentences(n["text"])[-1] if _sentences(n["text"]) else ""
        if s and "[vault:" not in s:
            added.append(f"- [ ] Site lesson: {s.rstrip('.')}")
    body = body + ("\n" + "\n".join(added[:4]) if added else "") + "\n"
    return {"body_md": body, "change_note": f"Added {len(added[:4])} item(s) from recent notes and your edits (local heuristics).",
            "learned_from": [n["id"] for n in notes[:2]]}
