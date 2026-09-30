from site_memory.redact import find_secrets, split_secrets


def test_codes_are_split_out():
    text = "Key safe code 4471 by back door. Alarm engineer code is 9021, user code 1234. Wi-Fi password: BlueFox77"
    red, secrets = split_secrets(text)
    labels = [s["label"] for s in secrets]
    assert labels == ["key safe code", "alarm engineer code", "user code", "wi-fi password"]
    for v in ("4471", "9021", "1234", "BlueFox77"):
        assert v not in red
    assert "[vault: key safe code]" in red


def test_ordinary_text_is_left_alone():
    for text in ("Postcode L18 4RT", "error code E119 on the boiler", "code of practice BS8418", "zone 4 pin chart"):
        assert find_secrets(text) == [], text


def test_uk_dates_are_not_flipped():
    from site_memory.agent import _fix_uk_dates

    facts = [{"service_due": "2026-12-10"}, {"warranty_until": "2027-03-01"}]
    _fix_uk_dates(facts, "Boiler service due 12/10/2026.")
    assert facts[0]["service_due"] == "2026-10-12"
    assert facts[1]["warranty_until"] == "2027-03-01"
