"""MN Labs Installs demo data. Every person, phone number and address is invented.

Phone numbers use Ofcom's reserved drama ranges (0151 496 0xxx, 07700 900xxx).
Dates are relative to the day the demo is seeded, so "tomorrow's route" always
has jobs on it and warranty / service flags always fall due in the demo window.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

SEED_MARK = "seed"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "item"


def fact_key(kind: str, label: str) -> str:
    return f"{kind}:{slug(label)}"


def seed_payload(today: date | None = None) -> tuple[dict, list[dict]]:
    """Return (memory_payload, vault_secrets). Secrets go to the encrypted vault only."""
    t = today or date.today()

    def d(days: int) -> str:
        return (t + timedelta(days=days)).isoformat()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    properties = [
        {"id": "p-01", "address": "12 Elm Grove", "town": "Liverpool", "postcode": "L18 4RT",
         "customer": "Joan Pritchard", "kind": "Semi-detached house", "tags": ["cctv", "alarm"]},
        {"id": "p-02", "address": "14 Oak Street", "town": "Birkenhead", "postcode": "CH41 5AB",
         "customer": "Dev Patel", "kind": "Victorian terrace", "tags": ["heating", "electrical", "smart home"]},
        {"id": "p-03", "address": "Unit 4, Canal Side Works", "town": "Bootle", "postcode": "L20 8EF",
         "customer": "Keel & Chisel Joinery (Sam Hughes)", "kind": "Light-industrial unit", "tags": ["cctv", "alarm", "commercial"]},
        {"id": "p-04", "address": "3 Rowan Close", "town": "Formby", "postcode": "L37 2GH",
         "customer": "Grace Okafor (son Tunde is app admin)", "kind": "Bungalow", "tags": ["alarm", "cctv", "vulnerable customer"]},
        {"id": "p-05", "address": "88 Larch Lane", "town": "Crosby", "postcode": "L23 9XY",
         "customer": "Priya Shah (landlord) via Waterloo Lettings", "kind": "Rented flat over two floors", "tags": ["landlord", "heating", "fire"]},
        {"id": "p-06", "address": "21 Willow Walk", "town": "West Kirby", "postcode": "CH48 3JQ",
         "customer": "Ellie & Marcus Doyle", "kind": "New-build detached", "tags": ["cctv", "survey"]},
    ]

    notes_raw = [
        # id, property, days ago, text
        ("n-0001", "p-01", -470, "12 Elm Grove: fitted 3x Hikvision DS-2CD2387G2-LU ColorVu turrets. Front drive (above the garage), rear garden (back-bedroom soffit), side passage. NVR is a Hikvision DS-7604NXI-K1 in the loft above the landing hatch. CAT6 goes up through the soffit into the loft. 3-year warranty on cameras and NVR."),
        ("n-0002", "p-01", -470, "Customer Joan Pritchard, prefers a call not a text: 0151 496 0418. Dog (Bramble) loose in the back garden, so ring before you open the side gate."),
        ("n-0003", "p-01", -340, f"Texecom Premier Elite 24 panel in the under-stairs cupboard. Ricochet wireless PIRs in lounge and kitchen. Engineer code [vault: alarm engineer code]. Annual service due {d(1)}."),
        ("n-0004", "p-01", -40, "Moved the NVR from the loft to the under-stairs cupboard next to the Texecom panel. The loft was hitting 38°C. Patch lead runs through the old alarm cable duct."),
        ("n-0005", "p-02", -800, "14 Oak St: Hager 10-way consumer unit in the hallway cupboard, split load with 2 RCDs. Loft lighting circuit not labelled."),
        ("n-0006", "p-02", -300, f"Worcester Bosch Greenstar 4000 25kW combi in the kitchen, left of the window. Flue out the side wall. Service due {d(12)}. 10-year guarantee registered."),
        ("n-0007", "p-02", -300, "Customer Dev Patel, text first: 07700 900214. Permit parking zone B, visitor permit is in the kitchen drawer, ask Dev. Side gate code [vault: side gate code]."),
        ("n-0008", "p-02", -90, "Fitted a Reolink video doorbell on the porch, powered from the old chime transformer. Nest Learning Thermostat (3rd gen) in the lounge, Heat Link next to the boiler."),
        ("n-0009", "p-02", -10, "Dev says the Nest isn't holding the schedule and drops back to 21°C. Possibly the Heat Link on OpenTherm needs re-pairing."),
        ("n-0010", "p-03", -200, "Unit 4 Canal Side: Dahua NVR4108HS-8P-4KS2 in the office comms cabinet. 4x Dahua IPC-HFW2441S bullets on the loading bay and yard, 1x Dahua dome in the office. Cables in galvanised trunking along the roller-shutter header."),
        ("n-0011", "p-03", -200, "Pyronix Enforcer 32 panel by the fire door. Keyholder Sam Hughes on site from 7:30, 07700 900587. Alarm user code [vault: alarm user code] (Sam's, don't use the master). Roller shutter must be up before 8 or the forklift can't get out, so park on the road."),
        ("n-0012", "p-03", -20, "Keel & Chisel adding 2 more cameras on the timber store. NVR has 8 PoE ports, 5 used. Commission the new cameras next visit."),
        ("n-0013", "p-04", -150, "Ajax Hub 2 Plus on the hallway shelf above the radiator. 3x Ajax MotionCam PIRs (hall, lounge, kitchen). Hikvision ColorVu bullet on the front of the garage. Hub warranty 2 years."),
        ("n-0014", "p-04", -150, "Mrs Okafor is 82. Allow extra time and explain everything twice; she likes a cup of tea first. Key safe by the back door, [vault: key safe code]."),
        ("n-0015", "p-04", -60, "Ajax app: Tunde (son) is the admin user and lives in Manchester. Any user changes go through him."),
        ("n-0016", "p-05", -352, f"88 Larch Lane: Ideal Logic+ C30 combi in the upstairs airing cupboard, warranty ends {d(20)}. Aico Ei3024 multi-sensor and heat alarms, hardwired and radio-linked, annual test due {d(5)}. Wylex NHRS consumer unit."),
        ("n-0017", "p-05", -352, "Landlord Priya Shah owns it; tenants are arranged through Waterloo Lettings (0151 496 0733). Access only with 24h notice to the tenant."),
        ("n-0018", "p-06", -7, "Survey at 21 Willow Walk: new build, wants 4 cameras (drive, front door, rear garden, side). BT Openreach ONT and Smart Hub in the hall cupboard. 2x dummy cameras on the front to come down. Loft access via bedroom 2, boarded. Wi-Fi password [vault: wifi password] on the back of the hub."),
        ("n-0019", "p-06", -7, "Ellie and Marcus Doyle both work from home, so keep the Wi-Fi up until 12. Marcus wants the NVR in the loft but the loft is uninsulated; recommend the hall cupboard."),
        ("n-0020", "p-01", -12, "Elm Grove follow-up: the front drive camera was alerting on every passing car all night. Narrowed the motion zone to the drive only and set the human/vehicle filter to human only. Joan much happier. Do this on every drive camera at handover, not after the complaint."),
        ("n-0021", "p-04", -5, "Rowan Close: kitchen Ajax MotionCam down to 18% battery after 5 months (cold kitchen). From now on swap batteries at the annual service if any device is under 40%, and carry spare CR123As."),
    ]
    notes = [
        {"id": nid, "property_id": pid, "text": text, "recorded_at": d(days), "source": SEED_MARK, "status": "active"}
        for nid, pid, days, text in notes_raw
    ]
    note_date = {n["id"]: n["recorded_at"] for n in notes}

    facts_raw = [
        # note, property, kind, label, value, extras
        ("n-0001", "p-01", "asset", "Front drive camera", "Hikvision ColorVu turret", {"make": "Hikvision", "model": "DS-2CD2387G2-LU", "location": "Above the garage", "installed": d(-470), "warranty_until": d(-470 + 1095)}),
        ("n-0001", "p-01", "asset", "Rear garden camera", "Hikvision ColorVu turret", {"make": "Hikvision", "model": "DS-2CD2387G2-LU", "location": "Back-bedroom soffit", "installed": d(-470), "warranty_until": d(-470 + 1095)}),
        ("n-0001", "p-01", "asset", "Side passage camera", "Hikvision ColorVu turret", {"make": "Hikvision", "model": "DS-2CD2387G2-LU", "location": "Side passage", "installed": d(-470), "warranty_until": d(-470 + 1095)}),
        ("n-0001", "p-01", "asset", "NVR", "Hikvision 4-channel NVR", {"make": "Hikvision", "model": "DS-7604NXI-K1", "location": "Loft, above the landing hatch", "installed": d(-470), "warranty_until": d(-470 + 1095)}),
        ("n-0001", "p-01", "cable", "Camera cable route", "CAT6 up through the soffit into the loft", {}),
        ("n-0002", "p-01", "customer", "Customer", "Joan Pritchard, prefers a call: 0151 496 0418", {}),
        ("n-0002", "p-01", "access", "Dog in garden", "Dog (Bramble) loose in the back garden, ring before opening the side gate", {}),
        ("n-0003", "p-01", "asset", "Alarm panel", "Texecom Premier Elite 24", {"make": "Texecom", "model": "Premier Elite 24", "location": "Under-stairs cupboard", "installed": d(-340), "service_due": d(1)}),
        ("n-0003", "p-01", "asset", "Wireless PIRs", "Texecom Ricochet PIRs x2", {"make": "Texecom", "model": "Ricochet", "location": "Lounge, kitchen", "installed": d(-340)}),
        ("n-0004", "p-01", "asset", "NVR", "Hikvision 4-channel NVR", {"make": "Hikvision", "model": "DS-7604NXI-K1", "location": "Under-stairs cupboard, next to the alarm panel"}),
        ("n-0004", "p-01", "cable", "NVR patch lead", "Runs through the old alarm cable duct", {}),
        ("n-0005", "p-02", "asset", "Consumer unit", "Hager 10-way, split load, 2 RCDs", {"make": "Hager", "model": "10-way split load", "location": "Hallway cupboard"}),
        ("n-0005", "p-02", "general", "Unlabelled circuit", "Loft lighting circuit not labelled", {}),
        ("n-0006", "p-02", "asset", "Boiler", "Worcester Bosch Greenstar 4000 25kW combi", {"make": "Worcester Bosch", "model": "Greenstar 4000 25kW", "location": "Kitchen, left of the window", "installed": d(-300), "service_due": d(12), "warranty_until": d(-300 + 3650)}),
        ("n-0007", "p-02", "customer", "Customer", "Dev Patel, text first: 07700 900214", {}),
        ("n-0007", "p-02", "access", "Parking", "Permit zone B; visitor permit in the kitchen drawer, ask Dev", {}),
        ("n-0008", "p-02", "asset", "Video doorbell", "Reolink video doorbell", {"make": "Reolink", "model": "Video Doorbell", "location": "Porch, on the old chime transformer", "installed": d(-90)}),
        ("n-0008", "p-02", "asset", "Thermostat", "Nest Learning Thermostat 3rd gen + Heat Link", {"make": "Google Nest", "model": "Learning Thermostat 3rd gen", "location": "Lounge; Heat Link next to the boiler", "installed": d(-90)}),
        ("n-0009", "p-02", "general", "Open issue", "Nest not holding schedule, drops to 21°C; Heat Link on OpenTherm may need re-pairing", {}),
        ("n-0010", "p-03", "asset", "NVR", "Dahua 8-channel PoE NVR", {"make": "Dahua", "model": "NVR4108HS-8P-4KS2", "location": "Office comms cabinet", "installed": d(-200)}),
        ("n-0010", "p-03", "asset", "Yard cameras", "Dahua bullets x4", {"make": "Dahua", "model": "IPC-HFW2441S", "location": "Loading bay and yard", "installed": d(-200)}),
        ("n-0010", "p-03", "asset", "Office dome", "Dahua dome", {"make": "Dahua", "model": "Dome", "location": "Office", "installed": d(-200)}),
        ("n-0010", "p-03", "cable", "Camera cable route", "Galvanised trunking along the roller-shutter header", {}),
        ("n-0011", "p-03", "asset", "Alarm panel", "Pyronix Enforcer 32", {"make": "Pyronix", "model": "Enforcer 32", "location": "By the fire door", "installed": d(-200)}),
        ("n-0011", "p-03", "customer", "Keyholder", "Sam Hughes, on site from 7:30, 07700 900587", {}),
        ("n-0011", "p-03", "access", "Roller shutter", "Shutter up before 8 or the forklift can't get out, so park on the road", {}),
        ("n-0012", "p-03", "general", "PoE capacity", "8 PoE ports, 5 used; 2 timber-store cameras to add", {}),
        ("n-0013", "p-04", "asset", "Alarm hub", "Ajax Hub 2 Plus", {"make": "Ajax", "model": "Hub 2 Plus", "location": "Hallway shelf above the radiator", "installed": d(-150), "warranty_until": d(-150 + 730)}),
        ("n-0013", "p-04", "asset", "PIRs", "Ajax MotionCam x3", {"make": "Ajax", "model": "MotionCam", "location": "Hall, lounge, kitchen", "installed": d(-150)}),
        ("n-0013", "p-04", "asset", "Garage camera", "Hikvision ColorVu bullet", {"make": "Hikvision", "model": "ColorVu bullet", "location": "Front of the garage", "installed": d(-150)}),
        ("n-0014", "p-04", "access", "Customer care", "Mrs Okafor is 82: allow extra time, explain twice, tea first", {}),
        ("n-0014", "p-04", "access", "Key safe", "Key safe by the back door (code in vault)", {}),
        ("n-0015", "p-04", "customer", "App admin", "Tunde Okafor (son, Manchester) is the Ajax admin; user changes go through him", {}),
        ("n-0016", "p-05", "asset", "Boiler", "Ideal Logic+ C30 combi", {"make": "Ideal", "model": "Logic+ C30", "location": "Upstairs airing cupboard", "installed": d(-352), "warranty_until": d(20)}),
        ("n-0016", "p-05", "asset", "Smoke / heat alarms", "Aico Ei3024 multi-sensor + heat, radio-linked", {"make": "Aico", "model": "Ei3024", "location": "Hall, landing, kitchen", "installed": d(-352), "service_due": d(5)}),
        ("n-0016", "p-05", "asset", "Consumer unit", "Wylex NHRS", {"make": "Wylex", "model": "NHRS", "location": "Under the stairs", "installed": d(-352)}),
        ("n-0017", "p-05", "customer", "Landlord", "Priya Shah; tenants via Waterloo Lettings 0151 496 0733", {}),
        ("n-0017", "p-05", "access", "Tenant notice", "Access only with 24h notice to the tenant", {}),
        ("n-0018", "p-06", "asset", "Router / ONT", "BT Openreach ONT + Smart Hub", {"make": "BT", "model": "Smart Hub", "location": "Hall cupboard"}),
        ("n-0018", "p-06", "asset", "Dummy cameras", "2x dummy cameras (to remove)", {"location": "Front elevation"}),
        ("n-0018", "p-06", "access", "Loft", "Loft access via bedroom 2, boarded", {}),
        ("n-0019", "p-06", "customer", "Customers", "Ellie & Marcus Doyle, both WFH: keep the Wi-Fi up until 12", {}),
        ("n-0019", "p-06", "general", "NVR location", "Marcus wants the loft; loft is uninsulated, recommend the hall cupboard", {}),
        ("n-0020", "p-01", "general", "Drive camera motion", "Zone narrowed to the drive; human-only filter (passing cars were alerting)", {}),
        ("n-0021", "p-04", "general", "PIR batteries", "Kitchen MotionCam at 18% after 5 months (cold kitchen); swap if under 40% at service", {}),
    ]
    facts = []
    for i, (nid, pid, kind, label, value, extra) in enumerate(facts_raw, start=1):
        f = {
            "id": f"f-{i:04d}", "property_id": pid, "kind": kind, "key": fact_key(kind, label),
            "label": label, "value": value, "make": "", "model": "", "location": "",
            "installed": "", "warranty_until": "", "service_due": "",
            "note_id": nid, "recorded_at": note_date[nid], "status": "active",
        }
        f.update(extra)
        facts.append(f)

    jobs = [
        {"id": "j-01", "property_id": "p-06", "date": d(1), "time": "08:30", "job_type": "cctv-install", "title": "4-camera install (drive, door, garden, side)"},
        {"id": "j-02", "property_id": "p-01", "date": d(1), "time": "12:30", "job_type": "alarm-service", "title": "Annual alarm service"},
        {"id": "j-03", "property_id": "p-02", "date": d(1), "time": "15:30", "job_type": "heating-fault", "title": "Nest not holding schedule + boiler check"},
        {"id": "j-04", "property_id": "p-03", "date": d(2), "time": "07:45", "job_type": "nvr-commission", "title": "Add + commission 2 timber-store cameras"},
        {"id": "j-05", "property_id": "p-05", "date": d(5), "time": "10:00", "job_type": "alarm-service", "title": "Landlord alarm test + boiler check"},
    ]

    def ver(v: int, days: int, body: str, note: str, source: str) -> dict:
        return {"version": v, "at": d(days), "body_md": body, "change_note": note, "source": source}

    spec_v1 = """# How I spec a 4-camera install

## Before quoting
- [ ] Walk the outside with the customer: drive, front door, rear garden, side
- [ ] Mark each camera position and the field of view on the phone photo
- [ ] Check the loft is boarded and has access for the cable run

## Kit
- [ ] 4x 4MP ColorVu turrets (white unless the soffit is black)
- [ ] 4-channel PoE NVR, 2TB drive
- [ ] CAT6 external grade + weatherproof junction boxes

## On the day
- [ ] Cables through the soffit, drip loop at every entry
- [ ] Set motion zones away from the pavement (privacy)
- [ ] Hand over the app on the customer's phone before leaving
"""
    spec_v2 = """# How I spec a 4-camera install

## Before quoting
- [ ] Walk the outside with the customer: drive, front door, rear garden, side
- [ ] Mark each camera position and the field of view on the phone photo
- [ ] Ask where the router / ONT lives *before* choosing the NVR spot
- [ ] Check the loft temperature: uninsulated loft = no NVR up there (keep it under 35°C)

## Kit
- [ ] 4x 4MP ColorVu turrets (white unless the soffit is black)
- [ ] 8-channel PoE NVR by default, so there's room to add cameras later
- [ ] 2TB drive minimum (about 14 days at 4MP on motion)
- [ ] CAT6 external grade + weatherproof junction boxes

## On the day
- [ ] Check the PoE budget against the camera spec sheet
- [ ] Cables through the soffit, drip loop at every entry
- [ ] Set motion zones away from the pavement (privacy / ICO guidance)
- [ ] Hand over the app on the customer's phone before leaving
- [ ] Photo of the NVR + cable labels into Site Memory
"""
    hik_v1 = """# Commissioning a Hikvision NVR

- [ ] Update NVR firmware before adding cameras
- [ ] Activate with a strong admin password, store it in the vault (never on a sticker)
- [ ] Set time zone to London + NTP (uk.pool.ntp.org), DST on
- [ ] Add cameras on PoE ports, check each shows the right channel name
- [ ] H.265+, 4MP, 15 fps main stream; sub-stream 640x360 for the app
- [ ] Motion / line-crossing zones drawn away from the pavement
- [ ] Format HDD, set overwrite on, confirm days of retention
- [ ] Hik-Connect: add to the customer's app, share view-only to family
- [ ] Record serial, firmware and location into Site Memory
"""
    alarm_v1 = """# Annual alarm service checklist

- [ ] Log in with the engineer code (from the vault)
- [ ] Walk test every detector
- [ ] Test the bell box and the internal sounder
- [ ] Check the panel battery
- [ ] Sign the service sheet
"""
    alarm_v2 = """# Annual alarm service checklist

- [ ] Tell the customer and the monitoring centre (if any) before you start
- [ ] Log in with the engineer code (from the vault)
- [ ] Read and photograph the event log before touching anything
- [ ] Walk test every detector; note any slow ones
- [ ] Test the bell box, strobe and internal sounder
- [ ] Panel battery: load test, replace if under 12.4 V
- [ ] Sign the service sheet
"""
    alarm_v3 = """# Annual alarm service checklist

- [ ] Tell the customer and the monitoring centre (if any) before you start
- [ ] Log in with the engineer code (from the vault)
- [ ] Read and photograph the event log before touching anything
- [ ] Walk test every detector; note any slow ones
- [ ] Wireless kit (Ricochet / Ajax): check signal strength + battery % per device
- [ ] Test the bell box, strobe and internal sounder; check the tamper
- [ ] Panel battery: load test, replace if under 12.4 V; bell box battery too
- [ ] Check the user codes with the customer, remove old ones
- [ ] Set the next service date in Site Memory
- [ ] Sign the service sheet, photo into Site Memory
"""
    boiler_v1 = """# Combi boiler fault visit: first 15 minutes

- [ ] Ask what it's doing and since when (heating, hot water, or both)
- [ ] Read the fault code / display before resetting anything
- [ ] Check the pressure gauge (1–1.5 bar cold)
- [ ] Check the thermostat / Heat Link is calling for heat
- [ ] Gas on at the meter, other appliances working?
- [ ] Condensate pipe frozen or blocked? (winter)
- [ ] Only then: flue analyser reading
"""
    skills = [
        {"id": "sk-01", "slug": "4-camera-install-spec", "title": "How I spec a 4-camera install",
         "summary": "Survey, kit list and install-day checks for a standard 4-camera domestic job.",
         "job_types": ["cctv-install"], "property_ids": ["p-06"], "learned_from": ["n-0001", "n-0004", "n-0018"],
         "versions": [ver(1, -120, spec_v1, "First draft learned from Elm Grove install notes", "nemotron"),
                      ver(2, -30, spec_v2, "Your edits: 8-channel NVR by default, router first, loft temperature, PoE budget", "edited")]},
        {"id": "sk-02", "slug": "commissioning-hikvision-nvr", "title": "Commissioning a Hikvision NVR",
         "summary": "Firmware, time, channels, retention and app handover for Hikvision NVRs.",
         "job_types": ["nvr-commission", "cctv-install"], "property_ids": ["p-01"], "learned_from": ["n-0001"],
         "versions": [ver(1, -200, hik_v1, "Learned from Elm Grove commissioning notes", "nemotron")]},
        {"id": "sk-03", "slug": "annual-alarm-service", "title": "Annual alarm service checklist",
         "summary": "Walk test, sounders, batteries, codes and paperwork for an annual intruder alarm service.",
         "job_types": ["alarm-service"], "property_ids": [], "learned_from": ["n-0003", "n-0013"],
         "versions": [ver(1, -400, alarm_v1, "Starter checklist", "seed"),
                      ver(2, -200, alarm_v2, "Your edits: tell the monitoring centre, event log first, battery threshold", "edited"),
                      ver(3, -45, alarm_v3, "Learned from Rowan Close + Elm Grove: wireless signal checks, tamper, user codes", "nemotron")]},
        {"id": "sk-04", "slug": "combi-fault-first-15", "title": "Combi boiler fault visit: first 15 minutes",
         "summary": "The order I check things on a no-heat / no-hot-water call before getting the analyser out.",
         "job_types": ["heating-fault"], "property_ids": ["p-02"], "learned_from": ["n-0006", "n-0009"],
         "versions": [ver(1, -60, boiler_v1, "Learned from Oak Street visits", "nemotron")]},
    ]
    for s in skills:
        latest = s["versions"][-1]
        s["version"] = latest["version"]
        s["body_md"] = latest["body_md"]
        s["updated_at"] = latest["at"]

    proposals = [
        {"id": "pr-0001", "kind": "skill_new", "status": "pending", "created_at": now,
         "source": "seed-demo", "model": "(seeded example)",
         "title": "New skill: Ajax wireless alarm handover",
         "summary": "Seeded example so the review queue isn't empty on first run. Run 'Learn a skill' for a live Nemotron proposal.",
         "payload": {"title": "Ajax wireless alarm handover",
                     "summary": "Getting the customer and their family set up on the Ajax app after install.",
                     "job_types": ["alarm-install"],
                     "learned_from": ["n-0013", "n-0015"],
                     "body_md": """# Ajax wireless alarm handover

- [ ] Agree who the admin is before leaving (a family member if the customer isn't app-confident)
- [ ] Install the Ajax app on the admin's phone and send the invite
- [ ] Add other users as "user" not "admin"
- [ ] Show arm / disarm / night mode twice, then let them do it
- [ ] Walk test every MotionCam with the customer watching the app
- [ ] Leave a printed one-page guide by the hub
- [ ] Record the admin's name and phone in Site Memory
"""}},
    ]

    journal = [
        {"id": "act-0001", "action": "seeded", "detail": "Demo memory loaded: 6 properties, 22 assets, 4 skills", "at": now},
    ]

    payload = {
        "business": "MN Labs Installs",
        "seeded_on": t.isoformat(),
        "properties": properties,
        "notes": notes,
        "facts": facts,
        "jobs": jobs,
        "skills": skills,
        "proposals": proposals,
        "decisions": [],
        "edit_signals": [],
        "journal": journal,
        "session": {},
        "nightly": None,
        "brief_cache": {},
        "llm_log": [],
    }
    secrets = [
        {"property_id": "p-01", "label": "alarm engineer code", "value": "7391", "note_id": "n-0003"},
        {"property_id": "p-02", "label": "side gate code", "value": "2580#", "note_id": "n-0007"},
        {"property_id": "p-03", "label": "alarm user code", "value": "6604", "note_id": "n-0011"},
        {"property_id": "p-04", "label": "key safe code", "value": "0482", "note_id": "n-0014"},
        {"property_id": "p-06", "label": "wifi password", "value": "MossyOtter-4417", "note_id": "n-0018"},
    ]
    return payload, secrets
