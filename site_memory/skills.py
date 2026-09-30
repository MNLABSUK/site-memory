"""Skill file helpers: markdown files on disk, checklist export, version diffs."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

HEADER_RE = re.compile(r"^<!--\s*site-memory skill:.*?-->\s*\n?", re.DOTALL)


def header(skill: dict) -> str:
    jt = ", ".join(skill.get("job_types") or []) or "any"
    return (
        f"<!-- site-memory skill: {skill['id']} v{skill['version']} | job types: {jt} | "
        "edit this file and Site Memory records your change as a new version -->\n"
    )


def strip_header(text: str) -> str:
    return HEADER_RE.sub("", text or "", count=1)


def write_skill_files(skills_dir: Path, skill: dict) -> Path:
    skills_dir.mkdir(parents=True, exist_ok=True)
    hist = skills_dir / "history"
    hist.mkdir(exist_ok=True)
    path = skills_dir / f"{skill['slug']}.md"
    path.write_text(header(skill) + skill["body_md"], encoding="utf-8")
    for v in skill.get("versions", []):
        hp = hist / f"{skill['slug']}.v{v['version']}.md"
        if not hp.exists():
            hp.write_text(v["body_md"], encoding="utf-8")
    return path


def normalise(md: str) -> str:
    return "\n".join(line.rstrip() for line in (md or "").strip().splitlines()) + "\n"


def diff_lines(old: str, new: str) -> list[dict]:
    """Line diff for the UI: [{op: '+'|'-'|' ', text}] (context trimmed)."""
    out: list[dict] = []
    for line in difflib.unified_diff(normalise(old).splitlines(), normalise(new).splitlines(), lineterm="", n=1):
        if line.startswith(("---", "+++", "@@")):
            continue
        op = line[:1] if line[:1] in "+-" else " "
        out.append({"op": op, "text": line[1:] if op != " " else line[1:]})
    return out


def edit_signal(old: str, new: str) -> dict:
    d = diff_lines(old, new)
    return {
        "added": [x["text"].strip() for x in d if x["op"] == "+" and x["text"].strip()],
        "removed": [x["text"].strip() for x in d if x["op"] == "-" and x["text"].strip()],
    }


def export_checklist(skill: dict, property_bundle: dict | None = None, business: str = "MN Labs Installs") -> str:
    """Plain-text checklist for a sub or apprentice. Never includes vault contents."""
    lines = [f"{business}: {skill['title']}", f"Skill v{skill['version']} · job types: {', '.join(skill.get('job_types') or []) or 'any'}", ""]
    if property_bundle:
        p = property_bundle["property"]
        lines += [f"SITE: {p['address']}, {p['town']} {p['postcode']}", f"Customer: {p.get('customer', '')}"]
        for f in property_bundle["facts"]:
            if f["kind"] == "access":
                lines.append(f"Access: {f['value']}")
        kit = [f for f in property_bundle["facts"] if f["kind"] == "asset"]
        for f in kit[:8]:
            where = f" ({f['location']})" if f.get("location") else ""
            lines.append(f"Kit: {f['label']}: {f.get('make', '')} {f.get('model', '')}".rstrip() + where)
        if property_bundle.get("secrets"):
            lines.append("Codes: ask Michael. Codes are never printed on checklists.")
        lines.append("")
    for raw in (skill.get("body_md") or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            title = s.lstrip("#").strip()
            if title == skill["title"]:
                continue
            lines += ["", title.upper()]
            continue
        s = re.sub(r"^(?:[-*]\s*\[[ xX]\]|[-*]|\d+[.)])\s*", "", s)
        s = s.replace("**", "").replace("*", "")
        lines.append(f"[ ] {s}")
    lines += ["", "Signed: ____________   Date: ________"]
    return "\n".join(lines).strip() + "\n"
