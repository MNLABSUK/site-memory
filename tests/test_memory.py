import hashlib
import json
import re

from site_memory.memory import MemoryStore

# Short sha256 prefixes of real client / business names that must never appear in demo data.
# (Stored as hashes so the names themselves are not published in this repo.)
_BANNED = {"b95e5330e7776ce7", "8fb7cf7a46995c95", "23fcab34442653e1", "b9c8934f436ed522", "e675137ec2f19377"}


def _grams(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}


def test_seed_shape(store):
    st = store.stats()
    assert st["properties"] == 6
    assert st["assets"] >= 20
    assert 3 <= st["skills"] <= 4
    assert st["vault"] == 5
    hashes = {hashlib.sha256(g.encode()).hexdigest()[:16] for g in _grams(json.dumps(store.snapshot()))}
    assert not hashes & _BANNED


def test_secrets_never_in_plain_memory_or_vault_file(store):
    raw_memory = store.path.read_text()
    raw_vault = store.vault.path.read_text()
    for secret in store.vault.plaintexts():
        assert secret not in raw_memory
        assert secret not in raw_vault


def test_flags_conflict_stale_due(store):
    flags = store.flags()
    kinds = {(f["type"], f["property_id"]) for f in flags}
    assert ("conflict", "p-01") in kinds          # NVR loft vs under-stairs
    assert ("stale", "p-02") in kinds             # consumer unit from 2024
    assert ("warranty_due", "p-05") in kinds      # boiler warranty in 20 days
    assert ("service_due", "p-01") in kinds       # alarm service tomorrow
    conflict = next(f for f in flags if f["type"] == "conflict")
    assert conflict["note_ids"][0] == "n-0004"    # newest first


def test_resolve_property(store):
    assert store.resolve_property("I'm at 14 Oak St, what do I need to know?")[0]["id"] == "p-02"
    assert store.resolve_property("12 elm grove")[0]["id"] == "p-01"
    assert store.resolve_property("canal side bootle")[0]["id"] == "p-03"
    assert store.resolve_property("99 Nowhere Road")[0] is None


def test_forget_and_redact(store):
    n_before = len(store.facts("p-02"))
    store.forget_fact("f-0012")                   # consumer unit
    assert len(store.facts("p-02")) == n_before - 1
    assert all(f["id"] != "f-0012" for f in store.llm_property_context("p-02")["facts"])

    fact = next(f for f in store.facts("p-02") if f["label"] == "Customer")
    phone = "07700 900214"
    assert phone in fact["value"]
    store.redact_fact(fact["id"])
    ctx = json.dumps(store.llm_property_context("p-02"))
    assert phone not in ctx
    assert phone in store.vault.plaintexts()[-1]


def test_forget_note_drops_its_facts(store):
    store.forget_note("n-0001")
    assert not [f for f in store.facts("p-01") if f["note_id"] == "n-0001"]
    assert not [f for f in store.flags("p-01") if f["type"] == "conflict"]


def test_memory_survives_restart(store, tmp_path):
    store.forget_fact("f-0001")
    again = MemoryStore(store.dir)
    assert again.get_fact("f-0001")["status"] == "forgotten"
    assert len(again.vault.list()) == 5
