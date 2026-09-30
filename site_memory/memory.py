"""Persistent property memory: properties, source notes, cited facts, jobs, skills,
the approval gate and a journal.

The storage core (thread lock + atomic JSON flush + journal + session + recall
scoring + digest) is carried over from Trade Memory. Everything property-, fact-,
vault-, skill- and gate-shaped is new for Site Memory.
"""

from __future__ import annotations

import json
import re
import threading
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from site_memory import skills as skillfiles
from site_memory.config import data_dir as default_data_dir
from site_memory.seed import fact_key, seed_payload, slug
from site_memory.vault import Vault

STALE_DAYS = 548          # ~18 months without anyone confirming a fact
DUE_WINDOW_DAYS = 45      # warranty / service falling due
ROUTE_DUE_WINDOW = 30

ACTIVE = "active"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> date:
    return date.today()


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _next_id(prefix: str, items: list[dict], width: int = 4) -> str:
    n = 0
    for it in items:
        m = re.match(rf"{re.escape(prefix)}-(\d+)$", str(it.get("id", "")))
        if m:
            n = max(n, int(m.group(1)))
    return f"{prefix}-{n + 1:0{width}d}"


_STOP = {"the", "at", "im", "i'm", "what", "do", "need", "to", "know", "on", "in", "a", "an", "i", "am",
         "for", "about", "st", "rd", "street", "road", "close", "lane", "walk", "grove", "me", "tell", "brief",
         "arriving", "here", "now", "whats", "what's", "there", "?"}
_ABBR = {"st": "street", "rd": "road", "ln": "lane", "cl": "close", "gr": "grove", "ave": "avenue"}


class MemoryStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.dir = Path(directory) if directory else default_data_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "memory.json"
        self.skills_dir = self.dir / "skills"
        self.vault = Vault(self.dir)
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self.load_or_seed()

    # ------------------------------------------------------------------ core
    def load_or_seed(self) -> None:
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._seed()

    def _seed(self) -> None:
        payload, secrets = seed_payload()
        self._data = payload
        self.vault.wipe()
        for s in secrets:
            self.vault.add(s["property_id"], s["label"], s["value"], note_id=s["note_id"])
        if self.skills_dir.exists():
            for p in self.skills_dir.rglob("*.md"):
                p.unlink()
        for sk in self._data["skills"]:
            skillfiles.write_skill_files(self.skills_dir, sk)
        self._flush()

    def reset_to_seed(self) -> None:
        with self._lock:
            self._seed()

    def _flush(self) -> None:
        self._data["updated_at"] = _now_iso()
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def log(self, action: str, detail: str = "", **extra: Any) -> dict:
        with self._lock:
            j = self._data.setdefault("journal", [])
            entry = {"id": _next_id("act", j), "action": action, "detail": detail[:240], "at": _now_iso(), **extra}
            j.append(entry)
            self._flush()
            return deepcopy(entry)

    def journal(self, limit: int = 60) -> list[dict]:
        with self._lock:
            return deepcopy(list(reversed(self._data.get("journal", [])))[:limit])

    def log_llm(self, meta: dict) -> None:
        with self._lock:
            log = self._data.setdefault("llm_log", [])
            log.append({**meta, "at": _now_iso()})
            del log[:-40]
            self._flush()

    def last_llm(self) -> dict | None:
        with self._lock:
            live = [m for m in self._data.get("llm_log", []) if m.get("source") == "nebius"]
            return deepcopy(live[-1]) if live else None

    def touch_session(self, **kw: Any) -> None:
        with self._lock:
            self._data.setdefault("session", {}).update({k: v for k, v in kw.items() if v is not None})
            self._flush()

    def session(self) -> dict:
        with self._lock:
            return deepcopy(self._data.get("session") or {})

    # ------------------------------------------------------------ properties
    def list_properties(self) -> list[dict]:
        with self._lock:
            props = deepcopy(self._data.get("properties", []))
            facts = [f for f in self._data.get("facts", []) if f.get("status") == ACTIVE]
        flags = self.flags()
        for p in props:
            pf = [f for f in facts if f["property_id"] == p["id"]]
            p["asset_count"] = len({f["key"] for f in pf if f["kind"] == "asset"})
            p["fact_count"] = len(pf)
            p["flag_count"] = sum(1 for fl in flags if fl["property_id"] == p["id"])
            p["label"] = f"{p['address']}, {p['town']}"
        return props

    def get_property(self, pid: str) -> dict | None:
        with self._lock:
            for p in self._data.get("properties", []):
                if p["id"] == pid:
                    return deepcopy(p)
        return None

    def resolve_property(self, query: str) -> tuple[dict | None, list[dict]]:
        """Find the property an installer means ("I'm at 14 Oak St"). Returns (best, candidates)."""
        q = (query or "").lower().replace(",", " ")
        tokens = [_ABBR.get(t, t) for t in re.findall(r"[a-z0-9&']+", q)]
        nums = {t for t in tokens if t.isdigit()}
        words = {t for t in tokens if not t.isdigit() and t not in _STOP and len(t) > 2}
        pc = re.findall(r"\b([a-z]{1,2}\d{1,2})\b", q)
        scored = []
        for p in self.list_properties():
            blob = f"{p['address']} {p['town']} {p['postcode']} {p['customer']}".lower()
            btoks = set(re.findall(r"[a-z0-9&']+", blob))
            score = 0.0
            addr_nums = set(re.findall(r"\d+", p["address"]))
            if nums & addr_nums:
                score += 2
            score += 3 * len(words & btoks)
            if any(c in p["postcode"].lower().split()[0:1] for c in pc):
                score += 2
            if nums and not (nums & addr_nums) and words & btoks:
                score -= 1
            if score > 0:
                scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        best = scored[0][1] if scored and scored[0][0] >= 3 else None
        return best, [p for _, p in scored[:4]]

    def create_property(self, address: str, town: str = "", postcode: str = "", customer: str = "", kind: str = "") -> dict:
        with self._lock:
            props = self._data.setdefault("properties", [])
            p = {"id": _next_id("p", props, 2), "address": address.strip(), "town": town.strip(),
                 "postcode": postcode.strip().upper(), "customer": customer.strip(), "kind": kind.strip(), "tags": []}
            props.append(p)
            self._flush()
            return deepcopy(p)

    # ----------------------------------------------------------------- facts
    def facts(self, pid: str | None = None, *, include_inactive: bool = False) -> list[dict]:
        with self._lock:
            fs = deepcopy(self._data.get("facts", []))
        if pid:
            fs = [f for f in fs if f["property_id"] == pid]
        if not include_inactive:
            fs = [f for f in fs if f.get("status") == ACTIVE]
        return fs

    def notes(self, pid: str | None = None, *, include_inactive: bool = False) -> list[dict]:
        with self._lock:
            ns = deepcopy(self._data.get("notes", []))
        if pid:
            ns = [n for n in ns if n.get("property_id") == pid]
        if not include_inactive:
            ns = [n for n in ns if n.get("status") == ACTIVE]
        return sorted(ns, key=lambda n: n.get("recorded_at", ""), reverse=True)

    def get_note(self, nid: str) -> dict | None:
        with self._lock:
            for n in self._data.get("notes", []):
                if n["id"] == nid:
                    return deepcopy(n)
        return None

    def get_fact(self, fid: str) -> dict | None:
        with self._lock:
            for f in self._data.get("facts", []):
                if f["id"] == fid:
                    return deepcopy(f)
        return None

    def flags(self, pid: str | None = None, today: date | None = None) -> list[dict]:
        """Conflicts, stale facts and warranties / services falling due."""
        t = today or _today()
        out: list[dict] = []
        fs = self.facts(pid)
        by_key: dict[tuple[str, str], list[dict]] = {}
        for f in fs:
            by_key.setdefault((f["property_id"], f["key"]), []).append(f)
        for (p, key), group in by_key.items():
            sigs = {(g["value"].strip().lower(), g.get("location", "").strip().lower()) for g in group}
            if len(group) > 1 and len(sigs) > 1:
                group = sorted(group, key=lambda g: g["recorded_at"], reverse=True)
                newest, older = group[0], group[1:]
                a = newest.get("location") or newest["value"]
                b = older[0].get("location") or older[0]["value"]
                out.append({"type": "conflict", "property_id": p, "fact_ids": [g["id"] for g in group],
                            "note_ids": [g["note_id"] for g in group], "label": newest["label"],
                            "message": f"{newest['label']}: newest note says “{a}”, older note says “{b}”. Using the newest; confirm on site and forget the wrong one."})
        for f in fs:
            rec = _parse_date(f.get("recorded_at"))
            if rec and (t - rec).days > STALE_DAYS:
                out.append({"type": "stale", "property_id": f["property_id"], "fact_ids": [f["id"]], "note_ids": [f["note_id"]],
                            "label": f["label"], "message": f"{f['label']} last confirmed {rec.strftime('%b %Y')} ({(t - rec).days // 30} months ago). Check it's still right."})
            for field, what in (("service_due", "Service"), ("warranty_until", "Warranty")):
                dd = _parse_date(f.get(field))
                if not dd:
                    continue
                days = (dd - t).days
                if -90 <= days <= DUE_WINDOW_DAYS:
                    when = "today" if days == 0 else "tomorrow" if days == 1 else (f"in {days} day{'s' if days != 1 else ''}" if days > 0 else f"{-days} days ago")
                    verb = "due" if what == "Service" else "ends"
                    out.append({"type": "service_due" if what == "Service" else "warranty_due", "property_id": f["property_id"],
                                "fact_ids": [f["id"]], "note_ids": [f["note_id"]], "label": f["label"], "date": dd.isoformat(), "days": days,
                                "message": f"{what} {verb} {when} on the {f['label'].lower()} ({f.get('make', '')} {f.get('model', '')}".rstrip() + ")"})
        return out

    def forget_fact(self, fid: str, reason: str = "") -> dict | None:
        with self._lock:
            for f in self._data.get("facts", []):
                if f["id"] == fid and f["status"] == ACTIVE:
                    f["status"] = "forgotten"
                    f["forgotten_at"] = _now_iso()
                    self._invalidate_brief(f["property_id"])
                    self._flush()
                    self.log("forgot", f"Forgot {f['label']} ({fid}) {reason}".strip(), property_id=f["property_id"], fact_id=fid)
                    return deepcopy(f)
        return None

    def redact_fact(self, fid: str) -> dict | None:
        """Move a fact's value into the encrypted vault and blank it everywhere else."""
        with self._lock:
            for f in self._data.get("facts", []):
                if f["id"] == fid and f["status"] == ACTIVE:
                    value = f["value"]
                    sec = self.vault.add(f["property_id"], f["label"].lower(), value, note_id=f["note_id"])
                    f["value"] = "[redacted: in vault]"
                    for fld in ("make", "model", "location"):
                        f[fld] = ""
                    f["status"] = "redacted"
                    f["vault_id"] = sec["id"]
                    for n in self._data.get("notes", []):
                        if n["id"] == f["note_id"] and value and value in n["text"]:
                            n["text"] = n["text"].replace(value, f"[vault: {f['label'].lower()}]")
                    self._invalidate_brief(f["property_id"])
                    self._flush()
                    self.log("redacted", f"Redacted {f['label']} ({fid}) into the vault", property_id=f["property_id"], fact_id=fid)
                    return deepcopy(f)
        return None

    def forget_note(self, nid: str) -> dict | None:
        with self._lock:
            for n in self._data.get("notes", []):
                if n["id"] == nid and n["status"] == ACTIVE:
                    n["status"] = "forgotten"
                    n["text"] = "(forgotten)"
                    for f in self._data.get("facts", []):
                        if f["note_id"] == nid and f["status"] == ACTIVE:
                            f["status"] = "forgotten"
                    self._invalidate_brief(n.get("property_id"))
                    self._flush()
                    self.log("forgot", f"Forgot note {nid} and every fact from it", property_id=n.get("property_id"), note_id=nid)
                    return deepcopy(n)
        return None

    def property_bundle(self, pid: str) -> dict | None:
        p = self.get_property(pid)
        if not p:
            return None
        facts = self.facts(pid)
        jobs = [j for j in self.jobs() if j["property_id"] == pid and (_parse_date(j["date"]) or _today()) >= _today()]
        return {
            "property": p,
            "facts": facts,
            "notes": self.notes(pid),
            "flags": self.flags(pid),
            "secrets": self.vault.list(pid),
            "skills": self.skills_for(pid, [j["job_type"] for j in jobs]),
            "jobs": jobs,
        }

    def llm_property_context(self, pid: str) -> dict:
        """Exactly what Nemotron is allowed to see about a property: redacted notes and
        cited facts. Vault contents are never included."""
        b = self.property_bundle(pid) or {}
        p = b.get("property", {})
        return {
            "property": {k: p.get(k) for k in ("id", "address", "town", "postcode", "customer", "kind")},
            "facts": [{k: f.get(k) for k in ("id", "kind", "label", "value", "make", "model", "location", "installed",
                                            "warranty_until", "service_due", "note_id", "recorded_at") if f.get(k)} for f in b.get("facts", [])],
            "notes": [{"id": n["id"], "date": n["recorded_at"], "text": n["text"]} for n in b.get("notes", [])][:12],
            "flags": [{"type": f["type"], "message": f["message"], "note_ids": f["note_ids"]} for f in b.get("flags", [])],
            "vault_items": [f"{s['label']} (kept in the encrypted vault, not shown)" for s in b.get("secrets", [])],
            "skills": [{"id": s["id"], "title": s["title"], "version": s["version"]} for s in b.get("skills", [])],
            "upcoming_jobs": [{"date": j["date"], "time": j["time"], "title": j["title"]} for j in b.get("jobs", [])],
        }

    def search(self, query: str, limit: int = 8) -> list[dict]:
        toks = [t for t in re.findall(r"[a-z0-9]+", (query or "").lower()) if len(t) > 2 and t not in _STOP]
        hits = []
        for n in self.notes():
            text = n["text"].lower()
            score = sum(1 for t in toks if t in text)
            if score:
                hits.append((score, n))
        hits.sort(key=lambda x: (-x[0], x[1]["recorded_at"]), reverse=False)
        return [n for _, n in hits[:limit]]

    # ----------------------------------------------------------- brief cache
    def _invalidate_brief(self, pid: str | None) -> None:
        if pid:
            self._data.setdefault("brief_cache", {}).pop(pid, None)

    def brief_fingerprint(self, pid: str) -> str:
        fs = self.facts(pid)
        return f"{len(fs)}:" + ",".join(sorted(f["id"] for f in fs)) + f":{_today().isoformat()}"

    def cached_brief(self, pid: str) -> dict | None:
        with self._lock:
            c = self._data.get("brief_cache", {}).get(pid)
        if c and c.get("fingerprint") == self.brief_fingerprint(pid):
            return deepcopy(c["brief"])
        return None

    def cache_brief(self, pid: str, brief: dict) -> None:
        with self._lock:
            self._data.setdefault("brief_cache", {})[pid] = {"fingerprint": self.brief_fingerprint(pid), "brief": brief}
            self._flush()

    # ------------------------------------------------------------------ jobs
    def jobs(self) -> list[dict]:
        with self._lock:
            return sorted(deepcopy(self._data.get("jobs", [])), key=lambda j: (j["date"], j["time"]))

    def next_route_date(self, after: date | None = None) -> str:
        start = (after or _today()) + timedelta(days=1)
        future = [j["date"] for j in self.jobs() if (_parse_date(j["date"]) or start) >= start]
        return min(future) if future else start.isoformat()

    def route(self, day: str | None = None) -> dict:
        """Deterministic route briefing for a day (default: tomorrow / next day with jobs)."""
        target = day or self.next_route_date()
        props = {p["id"]: p for p in self.list_properties()}
        items = []
        for j in [j for j in self.jobs() if j["date"] == target]:
            p = props.get(j["property_id"], {})
            facts = self.facts(j["property_id"])
            access = [f for f in facts if f["kind"] in ("access", "customer")]
            kit = [f for f in facts if f["kind"] == "asset"]
            items.append({
                "job": j,
                "property": p,
                "access": access,
                "kit": kit[:6],
                "flags": self.flags(j["property_id"]),
                "skills": self.skills_for(j["property_id"], [j["job_type"]]),
                "vault_count": len(self.vault.list(j["property_id"])),
            })
        t = _today()
        due = [f for f in self.flags() if f["type"] in ("service_due", "warranty_due") and f.get("days", 99) <= ROUTE_DUE_WINDOW]
        for d in due:
            p = props.get(d["property_id"], {})
            d["address"] = f"{p.get('address', '')}, {p.get('town', '')}"
            d["booked"] = any(j["property_id"] == d["property_id"] and j["date"] >= t.isoformat() for j in self.jobs())
        due.sort(key=lambda d: d.get("days", 0))
        return {"date": target, "jobs": items, "due": due}

    def set_nightly(self, result: dict) -> None:
        with self._lock:
            self._data["nightly"] = result
            self._flush()

    def nightly(self) -> dict | None:
        with self._lock:
            return deepcopy(self._data.get("nightly"))

    # ---------------------------------------------------------------- skills
    def skills(self) -> list[dict]:
        self.sync_skills_from_disk()
        with self._lock:
            return deepcopy(self._data.get("skills", []))

    def get_skill(self, sid: str) -> dict | None:
        for s in self.skills():
            if s["id"] == sid or s["slug"] == sid:
                return s
        return None

    def skills_for(self, pid: str | None, job_types: list[str] | None = None) -> list[dict]:
        jt = set(job_types or [])
        with self._lock:
            sk = deepcopy(self._data.get("skills", []))
        out = []
        for s in sk:
            why = []
            if pid and pid in s.get("property_ids", []):
                why.append("attached to this property")
            hit = jt & set(s.get("job_types", []))
            if hit:
                why.append("job type " + ", ".join(sorted(hit)))
            if why:
                out.append({"id": s["id"], "title": s["title"], "version": s["version"], "why": "; ".join(why)})
        return out

    def _add_skill_version(self, s: dict, body_md: str, change_note: str, source: str, proposal_id: str | None = None) -> None:
        v = s["version"] + 1
        s["versions"].append({"version": v, "at": _today().isoformat(), "body_md": body_md, "change_note": change_note,
                              "source": source, "proposal_id": proposal_id})
        s["version"], s["body_md"], s["updated_at"] = v, body_md, _today().isoformat()
        skillfiles.write_skill_files(self.skills_dir, s)

    def sync_skills_from_disk(self) -> list[str]:
        """If the installer edited a skill .md file by hand, record it as a new version."""
        changed = []
        with self._lock:
            for s in self._data.get("skills", []):
                path = self.skills_dir / f"{s['slug']}.md"
                if not path.exists():
                    skillfiles.write_skill_files(self.skills_dir, s)
                    continue
                body = skillfiles.strip_header(path.read_text(encoding="utf-8"))
                if skillfiles.normalise(body) != skillfiles.normalise(s["body_md"]):
                    sig = skillfiles.edit_signal(s["body_md"], body)
                    self._add_skill_version(s, body, "Edited by hand in the skill file", "edited-on-disk")
                    self._data.setdefault("edit_signals", []).append({"skill_id": s["id"], "at": _now_iso(), **sig})
                    changed.append(s["id"])
            if changed:
                self._flush()
        for sid in changed:
            self.log("skill_edited", f"Picked up hand edit to skill file {sid}", skill_id=sid)
        return changed

    def attach_skill(self, sid: str, *, property_id: str | None = None, job_type: str | None = None, detach: bool = False) -> dict | None:
        with self._lock:
            for s in self._data.get("skills", []):
                if s["id"] == sid:
                    for field, val in (("property_ids", property_id), ("job_types", job_type)):
                        if not val:
                            continue
                        lst = s.setdefault(field, [])
                        if detach and val in lst:
                            lst.remove(val)
                        elif not detach and val not in lst:
                            lst.append(val)
                    skillfiles.write_skill_files(self.skills_dir, s)
                    self._flush()
                    what = property_id or job_type
                    self.log("skill_detached" if detach else "skill_attached", f"{s['title']} {'from' if detach else 'to'} {what}", skill_id=sid)
                    return deepcopy(s)
        return None

    def edit_signals(self, skill_id: str | None = None, limit: int = 8) -> list[dict]:
        with self._lock:
            sig = deepcopy(self._data.get("edit_signals", []))
        if skill_id:
            sig = [s for s in sig if s.get("skill_id") in (skill_id, None)]
        return sig[-limit:]

    # ------------------------------------------------------------------ gate
    def add_proposal(self, kind: str, title: str, summary: str, payload: dict, *, source: str, model: str) -> dict:
        with self._lock:
            props = self._data.setdefault("proposals", [])
            pr = {"id": _next_id("pr", props), "kind": kind, "status": "pending", "title": title, "summary": summary,
                  "payload": payload, "source": source, "model": model, "created_at": _now_iso()}
            props.append(pr)
            self._flush()
        self.log("proposed", title, proposal_id=pr["id"], source=source)
        return deepcopy(pr)

    def proposals(self, status: str | None = None) -> list[dict]:
        with self._lock:
            ps = deepcopy(self._data.get("proposals", []))
        if status:
            ps = [p for p in ps if p["status"] in status.split(",")]
        return sorted(ps, key=lambda p: p["created_at"], reverse=True)

    def get_proposal(self, prid: str) -> dict | None:
        for p in self.proposals():
            if p["id"] == prid:
                return p
        return None

    def decide(self, prid: str, action: str, *, payload: dict | None = None, note: str = "") -> dict:
        """approve | edit (approve with your changes) | later | leave. Nothing is written
        to memory or skills except here, by a human."""
        if action not in ("approve", "edit", "later", "leave"):
            raise ValueError("action must be approve, edit, later or leave")
        with self._lock:
            pr = next((p for p in self._data.get("proposals", []) if p["id"] == prid), None)
            if pr is None:
                raise KeyError(prid)
            if pr["status"] in ("approved", "edited", "left"):
                raise ValueError(f"proposal already {pr['status']}")
            result: dict[str, Any] = {}
            if action in ("approve", "edit"):
                final = deepcopy(payload) if (action == "edit" and payload) else deepcopy(pr["payload"])
                result = self._apply(pr, final, edited=(action == "edit"))
                pr["status"] = "edited" if action == "edit" else "approved"
                pr["final_payload"] = final
            elif action == "later":
                pr["status"] = "later"
            else:
                pr["status"] = "left"
            pr["decided_at"] = _now_iso()
            pr["decision_note"] = note
            decs = self._data.setdefault("decisions", [])
            decs.append({"id": _next_id("dec", decs), "proposal_id": prid, "kind": pr["kind"], "decision": action,
                         "note": note, "at": _now_iso()})
            self._flush()
        verb = {"approve": "approved", "edit": "approved with edits", "later": "parked for later", "leave": "left"}[action]
        self.log(action if action != "edit" else "edited", f"{pr['title']}: {verb}", proposal_id=prid)
        return {"proposal": deepcopy(pr), **result}

    def _apply(self, pr: dict, payload: dict, *, edited: bool) -> dict:
        kind = pr["kind"]
        if kind == "memory":
            return self._apply_memory(pr, payload, edited=edited)
        if kind == "skill_new":
            sks = self._data.setdefault("skills", [])
            title = payload.get("title") or "Untitled skill"
            base = slug(title)[:48]
            sl = base
            i = 2
            while any(s["slug"] == sl for s in sks):
                sl, i = f"{base}-{i}", i + 1
            body = payload.get("body_md") or f"# {title}\n"
            sk = {"id": _next_id("sk", sks, 2), "slug": sl, "title": title, "summary": payload.get("summary", ""),
                  "job_types": [slug(j) for j in payload.get("job_types", []) if j], "property_ids": payload.get("property_ids", []),
                  "learned_from": payload.get("learned_from", []), "version": 1, "body_md": body, "updated_at": _today().isoformat(),
                  "versions": [{"version": 1, "at": _today().isoformat(), "body_md": body, "proposal_id": pr["id"],
                                "change_note": "Proposed by Nemotron" + (", edited by you before approving" if edited else ", approved as proposed"),
                                "source": "edited" if edited else pr.get("source", "nemotron")}]}
            if edited:
                self._record_edit(sk["id"], pr["payload"].get("body_md", ""), body)
            sks.append(sk)
            skillfiles.write_skill_files(self.skills_dir, sk)
            return {"skill": deepcopy(sk)}
        if kind == "skill_update":
            s = next((s for s in self._data.get("skills", []) if s["id"] == payload.get("skill_id")), None)
            if s is None:
                raise KeyError(payload.get("skill_id"))
            body = payload.get("body_md") or s["body_md"]
            note = payload.get("change_note") or "Improved"
            if edited:
                self._record_edit(s["id"], pr["payload"].get("body_md", ""), body)
                note += " (edited by you before approving)"
            self._add_skill_version(s, body, note, "edited" if edited else pr.get("source", "nemotron"), pr["id"])
            return {"skill": deepcopy(s)}
        raise ValueError(f"unknown proposal kind {kind}")

    def _record_edit(self, skill_id: str, old: str, new: str) -> None:
        sig = skillfiles.edit_signal(old, new)
        if sig["added"] or sig["removed"]:
            self._data.setdefault("edit_signals", []).append({"skill_id": skill_id, "at": _now_iso(), **sig})

    def _apply_memory(self, pr: dict, payload: dict, *, edited: bool) -> dict:
        pid = payload.get("property_id")
        created = None
        if not pid:
            np_ = payload.get("new_property") or {}
            if not np_.get("address"):
                raise ValueError("memory proposal needs a property_id or new_property.address")
            created = self.create_property(np_.get("address", ""), np_.get("town", ""), np_.get("postcode", ""), np_.get("customer", ""), np_.get("kind", ""))
            pid = created["id"]
        notes = self._data.setdefault("notes", [])
        note = {"id": _next_id("n", notes), "property_id": pid, "text": payload.get("note_text", "").strip(),
                "recorded_at": _today().isoformat(), "source": "capture", "status": ACTIVE, "proposal_id": pr["id"]}
        notes.append(note)
        facts = self._data.setdefault("facts", [])
        new_facts = []
        for f in payload.get("facts", []):
            if f.get("drop"):
                continue
            kind = f.get("kind") if f.get("kind") in ("asset", "access", "cable", "customer", "warranty", "service", "general") else "general"
            label = (f.get("label") or kind).strip()[:60]
            nf = {"id": _next_id("f", facts), "property_id": pid, "kind": kind, "key": fact_key(kind, label), "label": label,
                  "value": str(f.get("value", "")).strip()[:200], "make": str(f.get("make", "") or "")[:40], "model": str(f.get("model", "") or "")[:60],
                  "location": str(f.get("location", "") or "")[:80], "installed": _clean_date(f.get("installed")),
                  "warranty_until": _clean_date(f.get("warranty_until")), "service_due": _clean_date(f.get("service_due")),
                  "note_id": note["id"], "recorded_at": note["recorded_at"], "status": ACTIVE}
            facts.append(nf)
            new_facts.append(nf)
        secrets = []
        for s in payload.get("sealed_secrets", []):
            secrets.append(self.vault.add_sealed(pid, s["label"], s["token"], note_id=note["id"]))
        self._invalidate_brief(pid)
        return {"note": deepcopy(note), "facts": deepcopy(new_facts), "secrets": secrets, "created_property": created}

    # ----------------------------------------------------------------- stats
    def stats(self) -> dict:
        fs = self.facts()
        with self._lock:
            ps = self._data.get("proposals", [])
            n_sk = len(self._data.get("skills", []))
            n_props = len(self._data.get("properties", []))
        return {
            "properties": n_props,
            "assets": len({(f["property_id"], f["key"]) for f in fs if f["kind"] == "asset"}),
            "facts": len(fs),
            "notes": len(self.notes()),
            "skills": n_sk,
            "pending": sum(1 for p in ps if p["status"] == "pending"),
            "later": sum(1 for p in ps if p["status"] == "later"),
            "flags": len(self.flags()),
            "vault": len(self.vault.list()),
        }


def _clean_date(v: Any) -> str:
    d = _parse_date(str(v)) if v else None
    return d.isoformat() if d else ""


_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


def set_store(s: MemoryStore) -> None:
    global _store
    _store = s
