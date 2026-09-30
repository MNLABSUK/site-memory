import json


def test_routes_are_distinct_from_desk_gate(client):
    paths = {r.path for r in client.app.routes}
    assert "/api/decide" not in paths and "/api/followup" not in paths
    for p in ("/api/arrive", "/api/capture", "/api/review/{prid}", "/api/route/nightly", "/api/skills/learn"):
        assert p in paths


def test_status_dry_run(client):
    s = client.get("/api/status").json()
    assert s["mode"] == "dry-run"
    assert s["business"] == "MN Labs Installs"


def test_arrival_brief_is_cited(client, store):
    b = client.post("/api/arrive", json={"query": "I'm at 12 Elm Grove"}).json()
    assert b["resolved"] and b["property"]["id"] == "p-01"
    note_ids = set(b["notes"])
    assert b["summary"]["bullets"]
    for bullet in b["summary"]["bullets"]:
        assert bullet["cites"] and set(bullet["cites"]) <= note_ids
    assert any(f["type"] == "conflict" for f in b["flags"])
    assert all("token" not in s for s in b["secrets"])
    assert "7391" not in json.dumps(b)            # the alarm engineer code


def test_unknown_address_offers_candidates(client):
    b = client.post("/api/arrive", json={"query": "I'm at 99 Nowhere Road"}).json()
    assert b["resolved"] is False


def test_capture_waits_for_approval(client, store):
    facts_before = len(store.facts())
    r = client.post("/api/capture", json={"property_id": "p-02",
                                          "text": "Fitted Hikvision turret over the back door. New key safe by the side gate, key safe code 5519."}).json()
    pr = r["proposal"]
    assert pr["status"] == "pending" and pr["kind"] == "memory"
    assert "5519" not in json.dumps(r)
    assert "sealed_secrets" not in pr["payload"]
    assert len(store.facts()) == facts_before     # nothing saved yet

    d = client.post(f"/api/review/{pr['id']}", json={"action": "approve"}).json()
    assert d["proposal"]["status"] == "approved"
    assert len(store.facts()) > facts_before
    assert "5519" in store.vault.plaintexts()
    assert "5519" not in store.path.read_text()
    assert "[vault: key safe code]" in store.get_note(d["note"]["id"])["text"]


def test_leave_and_later(client, store):
    facts_before = len(store.facts())
    pr = client.post("/api/capture", json={"property_id": "p-04", "text": "Ajax hub moved to the hall cupboard."}).json()["proposal"]
    assert client.post(f"/api/review/{pr['id']}", json={"action": "later"}).json()["proposal"]["status"] == "later"
    assert len(store.facts()) == facts_before
    assert client.post(f"/api/review/{pr['id']}", json={"action": "leave"}).json()["proposal"]["status"] == "left"
    assert len(store.facts()) == facts_before
    assert client.post(f"/api/review/{pr['id']}", json={"action": "approve"}).status_code == 400


def test_edit_before_approve_drops_a_fact(client, store):
    r = client.post("/api/capture", json={"text": "5 Hazel Mews, Wallasey CH45: Hikvision NVR in the loft. Dog in the garden.",
                                          "address": "5 Hazel Mews, Wallasey"}).json()
    pr = r["proposal"]
    payload = pr["payload"]
    assert payload["new_property"]["address"]
    payload["facts"][0]["drop"] = True
    kept = [f for f in payload["facts"] if not f.get("drop")]
    d = client.post(f"/api/review/{pr['id']}", json={"action": "edit", "payload": payload}).json()
    assert d["proposal"]["status"] == "edited"
    assert d["created_property"]["id"] == "p-07"
    assert len(d["facts"]) == len(kept)


def test_new_skill_through_gate(client, store):
    r = client.post("/api/skills/learn", json={"topic": "Commissioning a Dahua NVR", "job_type": "nvr-commission"}).json()
    pr = r["proposal"]
    assert pr["kind"] == "skill_new" and pr["status"] == "pending"
    n_before = len(store.skills())
    d = client.post(f"/api/review/{pr['id']}", json={"action": "approve"}).json()
    assert len(store.skills()) == n_before + 1
    sk = d["skill"]
    assert sk["version"] == 1
    assert (store.skills_dir / f"{sk['slug']}.md").exists()


def test_skill_versioning_learns_from_edits(client, store):
    r = client.post("/api/skills/sk-03/improve").json()
    assert r["proposal"], r
    pr = r["proposal"]
    body = pr["payload"]["body_md"].rstrip() + "\n- [ ] Photo of the panel service label\n"
    d = client.post(f"/api/review/{pr['id']}", json={"action": "edit", "payload": {**pr["payload"], "body_md": body}}).json()
    sk = d["skill"]
    assert sk["version"] == 4 and sk["versions"][-1]["source"] == "edited"
    assert (store.skills_dir / "history" / "annual-alarm-service.v4.md").exists()
    assert any("Photo of the panel service label" in a for s in store.edit_signals("sk-03") for a in s["added"])
    detail = client.get("/api/skills/sk-03").json()
    assert len(detail["diffs"]) == 3


def test_hand_edit_of_skill_file_becomes_a_version(client, store):
    path = store.skills_dir / "combi-fault-first-15.md"
    path.write_text(path.read_text() + "- [ ] Check the filling loop is closed\n")
    sk = next(s for s in client.get("/api/skills").json()["skills"] if s["id"] == "sk-04")
    assert sk["version"] == 2 and sk["versions"][-1]["source"] == "edited-on-disk"


def test_checklist_export_has_no_codes(client, store):
    txt = client.get("/api/skills/sk-03/checklist", params={"property_id": "p-01"}).text
    assert "[ ]" in txt and "12 Elm Grove" in txt
    for secret in store.vault.plaintexts():
        assert secret not in txt


def test_attach_skill(client):
    s = client.post("/api/skills/sk-02/attach", json={"property_id": "p-03"}).json()["skill"]
    assert "p-03" in s["property_ids"]


def test_route_and_nightly(client):
    r = client.get("/api/route").json()["route"]
    assert len(r["jobs"]) == 3
    assert any(d["type"] == "warranty_due" for d in r["due"])
    assert all(j["skills"] for j in r["jobs"])
    n = client.post("/api/route/nightly").json()["nightly"]
    assert n["source"] == "dry-run" and n["jobs"]
    assert client.get("/api/route").json()["nightly"]["for_date"] == r["date"]


def test_vault_reveal_is_logged(client, store):
    sid = client.get("/api/vault", params={"property_id": "p-04"}).json()["secrets"][0]["id"]
    assert client.post(f"/api/vault/{sid}/reveal").json()["value"] == "0482"
    assert store.journal(1)[0]["action"] == "vault_reveal"
