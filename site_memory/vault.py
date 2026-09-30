"""Encrypted secrets store (Fernet / AES-128-CBC + HMAC).

Secrets live in ``data/vault.json`` as ciphertext; the key lives in
``data/vault.key`` (chmod 600). Nothing in here is ever passed to the LLM.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Vault:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.key_path = self.dir / "vault.key"
        self.path = self.dir / "vault.json"
        self._lock = threading.Lock()
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            os.chmod(self.key_path, 0o600)
        self._f = Fernet(self.key_path.read_bytes())
        self._items: list[dict] = []
        if self.path.exists():
            self._items = json.loads(self.path.read_text(encoding="utf-8"))

    def _flush(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._items, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        os.chmod(self.path, 0o600)

    # tokens let a pending (unapproved) proposal hold a secret without plaintext on disk
    def seal(self, value: str) -> str:
        return self._f.encrypt(value.encode("utf-8")).decode("ascii")

    def unseal(self, token: str) -> str:
        return self._f.decrypt(token.encode("ascii")).decode("utf-8")

    def add_sealed(self, property_id: str | None, label: str, token: str, *, note_id: str | None = None) -> dict:
        with self._lock:
            item = {
                "id": f"sec-{len(self._items) + 1:03d}",
                "property_id": property_id,
                "label": label,
                "token": token,
                "note_id": note_id,
                "created_at": _now_iso(),
                "status": "active",
            }
            self._items.append(item)
            self._flush()
            return self.masked(item)

    def add(self, property_id: str | None, label: str, value: str, *, note_id: str | None = None) -> dict:
        return self.add_sealed(property_id, label, self.seal(value), note_id=note_id)

    @staticmethod
    def masked(item: dict) -> dict:
        return {k: v for k, v in item.items() if k != "token"} | {"masked": "••••"}

    def list(self, property_id: str | None = None) -> list[dict]:
        with self._lock:
            items = [i for i in self._items if i.get("status") == "active"]
        if property_id:
            items = [i for i in items if i.get("property_id") == property_id]
        return [self.masked(i) for i in items]

    def reveal(self, secret_id: str) -> str | None:
        with self._lock:
            for i in self._items:
                if i["id"] == secret_id and i.get("status") == "active":
                    return self.unseal(i["token"])
        return None

    def delete(self, secret_id: str) -> bool:
        with self._lock:
            for i in self._items:
                if i["id"] == secret_id:
                    i["status"] = "deleted"
                    i["token"] = ""
                    self._flush()
                    return True
        return False

    def plaintexts(self) -> list[str]:
        """Test helper: every active secret value (used to prove none reach the LLM)."""
        with self._lock:
            return [self.unseal(i["token"]) for i in self._items if i.get("status") == "active" and i.get("token")]

    def wipe(self) -> None:
        with self._lock:
            self._items = []
            self._flush()
