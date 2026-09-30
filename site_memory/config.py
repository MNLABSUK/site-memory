"""Runtime configuration for Site Memory."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
DEFAULT_NIGHTLY_MODEL = "nvidia/nemotron-3-super-120b-a12b"
DEFAULT_PORT = 43167
BUSINESS_NAME = "MN Labs Installs"


def data_dir() -> Path:
    return Path(os.getenv("SITE_MEMORY_DATA_DIR") or (ROOT / "data"))


def get_settings() -> dict:
    """Read settings fresh each call so tests (and .env edits) take effect."""
    api_key = (os.getenv("NEBIUS_API_KEY") or "").strip()
    model = (os.getenv("NEBIUS_MODEL") or "").strip() or DEFAULT_MODEL
    nightly = (os.getenv("NEBIUS_NIGHTLY_MODEL") or "").strip() or DEFAULT_NIGHTLY_MODEL
    skills_model = (os.getenv("NEBIUS_SKILLS_MODEL") or "").strip() or nightly
    return {
        "api_key": api_key,
        "base_url": (os.getenv("NEBIUS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
        "model": model,
        "nightly_model": nightly,
        "skills_model": skills_model,
        "dry_run": not bool(api_key),
        "nightly_at": (os.getenv("SITE_MEMORY_NIGHTLY_AT") or "20:30").strip(),
        "port": int(os.getenv("SITE_MEMORY_PORT") or DEFAULT_PORT),
        "data_dir": str(data_dir()),
    }
