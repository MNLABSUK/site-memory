"""Local secret detection. Runs BEFORE anything is shown to Nemotron.

Alarm codes, key-safe codes, gate PINs and passwords are pulled out of free text
on the Mac, encrypted into the vault, and replaced with a placeholder such as
``[vault: key safe code]``. The LLM only ever sees the placeholder.
"""

from __future__ import annotations

import re

_PREFIX = r"(?:alarm|nvr|dvr|router|wi-?fi|app|panel|cctv)"
_KIND = (
    r"(?:engineer|master|user|installer|admin|duress|key\s?safe|keysafe|lock\s?box|"
    r"gate|door|garage|shutter|safe|side\s?gate|entry|wi-?fi)"
)
_WORD = r"(?:code|pin|passcode|password|pass|pw)"

SECRET_RE = re.compile(
    rf"\b(?P<label>(?:{_PREFIX}\s+)?(?:{_KIND}\s+)?{_WORD}|{_PREFIX}\s+{_KIND}|{_KIND}\s+{_WORD})"
    r"(?P<sep>\s*(?:is|was|now|=|:|-|–|—)?\s*)"
    r"(?P<value>[#*]?[A-Za-z0-9#*!@$%^&._-]{3,24})",
    re.IGNORECASE,
)

PLACEHOLDER_RE = re.compile(r"\[vault: [^\]]+\]|\[redacted[^\]]*\]")


def _looks_secret(label: str, value: str) -> bool:
    v = value.strip(".,;")
    if not v or v.lower() in {"the", "for", "and", "unknown", "changed", "reset", "vault", "in", "not"}:
        return False
    if re.search(r"password|pass|pw", label, re.I):
        return len(v) >= 4
    if re.fullmatch(r"(?:code|pin|passcode)", label, re.I):
        # a bare "code"/"pin" only counts when followed by something PIN-shaped
        return bool(re.fullmatch(r"[#*]?\d{3,10}[#*]?", v))
    return bool(re.search(r"\d", v))


def find_secrets(text: str) -> list[dict]:
    found: list[dict] = []
    for m in SECRET_RE.finditer(text or ""):
        label = re.sub(r"\s+", " ", m.group("label").strip().lower())
        value = m.group("value").rstrip(".,;")
        if _looks_secret(label, value):
            found.append({"label": label, "value": value, "start": m.start(), "end": m.end()})
    return found


def split_secrets(text: str) -> tuple[str, list[dict]]:
    """Return (redacted_text, secrets). Secrets carry label + plaintext value."""
    secrets = find_secrets(text)
    if not secrets:
        return text, []
    out, cursor = [], 0
    for s in secrets:
        out.append(text[cursor : s["start"]])
        out.append(f"[vault: {s['label']}]")
        cursor = s["end"]
    out.append(text[cursor:])
    return "".join(out), [{"label": s["label"], "value": s["value"]} for s in secrets]


def scrub(text: str) -> str:
    """Defence in depth: strip anything secret-shaped from an outbound LLM payload."""
    return split_secrets(text)[0]
