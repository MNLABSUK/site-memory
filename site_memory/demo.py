"""Public-demo guard rails (only active when SITE_MEMORY_DEMO=1).

The hosted demo shares one MN Labs sample memory between visitors, so it:
- rate-limits every write and every AI call per visitor IP, with a global
  hourly and daily ceiling on Nemotron calls to protect the Token Factory key;
- resets the demo data back to the seed on a schedule (default every 30 min).

Nothing here runs on a normal local install.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

# POST routes that can trigger a Nemotron (or Tavily) call
AI_PREFIXES = ("/api/arrive", "/api/capture", "/api/route/nightly", "/api/skills/learn", "/api/lookup")
AI_SUFFIXES = ("/improve", "/lookup")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def enabled() -> bool:
    return (os.getenv("SITE_MEMORY_DEMO") or "").strip().lower() in ("1", "true", "yes", "on")


def settings() -> dict:
    return {
        "reset_every_min": _int("SITE_MEMORY_DEMO_RESET_MIN", 30),
        "ai_per_ip_10min": _int("SITE_MEMORY_DEMO_AI_PER_IP", 20),
        "writes_per_ip_min": _int("SITE_MEMORY_DEMO_WRITES_PER_IP", 30),
        "ai_per_hour": _int("SITE_MEMORY_DEMO_AI_PER_HOUR", 240),
        "ai_per_day": _int("SITE_MEMORY_DEMO_AI_PER_DAY", 1500),
    }


def is_ai_route(method: str, path: str) -> bool:
    if method != "POST":
        return False
    return path.startswith(AI_PREFIXES) or path.endswith(AI_SUFFIXES)


class RateLimiter:
    """In-memory sliding windows. Good enough for one small demo instance."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque] = defaultdict(deque)

    def _take(self, key: str, limit: int, window_s: float, now: float) -> float | None:
        q = self._hits[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            return max(1.0, q[0] + window_s - now)
        q.append(now)
        return None

    def check(self, ip: str, method: str, path: str, now: float | None = None) -> tuple[bool, str, int]:
        """Returns (allowed, message, retry_after_seconds)."""
        if method not in ("POST", "PUT", "PATCH", "DELETE"):
            return True, "", 0
        now = time.monotonic() if now is None else now
        cfg = settings()
        with self._lock:
            wait = self._take(f"w:{ip}", cfg["writes_per_ip_min"], 60, now)
            if wait:
                return False, "Slow down a little: too many actions from you in the last minute.", int(wait)
            if is_ai_route(method, path):
                for key, limit, window, msg in (
                    (f"ai:{ip}", cfg["ai_per_ip_10min"], 600, "Demo limit reached: you've made a lot of Nemotron calls in 10 minutes."),
                    ("ai:hour", cfg["ai_per_hour"], 3600, "The public demo is busy: hourly Nemotron budget used."),
                    ("ai:day", cfg["ai_per_day"], 86400, "The public demo has used today's Nemotron budget."),
                ):
                    wait = self._take(key, limit, window, now)
                    if wait:
                        return False, f"{msg} Try again in about {max(1, int(wait) // 60 or 1)} min.", int(wait)
        return True, "", 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(headers, fallback: str | None) -> str:
    fwd = headers.get("x-forwarded-for") or ""
    if fwd:
        return fwd.split(",")[0].strip()
    return headers.get("x-real-ip") or fallback or "unknown"


class ResetClock:
    """Tracks when the shared demo memory is next restored to the seed."""

    def __init__(self) -> None:
        self.last_reset = datetime.now()

    def every(self) -> timedelta:
        return timedelta(minutes=max(1, settings()["reset_every_min"]))

    def next_reset(self) -> datetime:
        return self.last_reset + self.every()

    def due(self, now: datetime | None = None) -> bool:
        return (now or datetime.now()) >= self.next_reset()

    def mark(self, now: datetime | None = None) -> None:
        self.last_reset = now or datetime.now()


clock = ResetClock()


def status() -> dict | None:
    if not enabled():
        return None
    cfg = settings()
    return {
        "reset_every_min": cfg["reset_every_min"],
        "next_reset_at": clock.next_reset().isoformat(timespec="seconds"),
        "ai_per_ip_10min": cfg["ai_per_ip_10min"],
    }
