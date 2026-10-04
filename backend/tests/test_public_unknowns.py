"""Unknowns surface: public endpoints expose only world unknowns (B, D).

Internal unknowns (A: reality/ops, C: system/meta) stay owner-console only.
Counts by state use the engine's real state names from docs/UNKNOWN_MAP.md.
"""

from fastapi.testclient import TestClient

from app.api.public import (
    _parse_unknowns,
    PUBLIC_UNKNOWN_CATEGORIES,
    INTERNAL_UNKNOWN_CATEGORIES,
    _UNKNOWN_STATES,
)
from app.main import app

client = TestClient(app)


def test_parse_finds_unknowns_with_real_states():
    unknowns, _ = _parse_unknowns()
    assert unknowns, "no unknowns parsed from docs/UNKNOWN_MAP.md"
    states = {u["state"] for u in unknowns}
    assert states <= set(_UNKNOWN_STATES), f"invented states: {states - set(_UNKNOWN_STATES)}"


def test_public_categories_exclude_internal():
    unknowns, _ = _parse_unknowns()
    public = [u for u in unknowns if u["category"] in PUBLIC_UNKNOWN_CATEGORIES]
    internal = [u for u in unknowns if u["category"] in INTERNAL_UNKNOWN_CATEGORIES]
    assert public, "no public unknowns"
    assert internal, "no internal unknowns (separation untested)"
    assert not (set(PUBLIC_UNKNOWN_CATEGORIES) & set(INTERNAL_UNKNOWN_CATEGORIES))


def test_summary_endpoint_counts_only_public():
    unknowns, _ = _parse_unknowns()
    expected_public = [u for u in unknowns if u["category"] in PUBLIC_UNKNOWN_CATEGORIES]
    res = client.get("/api/public/unknowns/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == len(expected_public)
    assert set(body["counts"].keys()) == set(_UNKNOWN_STATES)
    assert sum(body["counts"].values()) == len(expected_public)
    # last_loop is a date string or null — never invented
    assert body["last_loop"] is None or isinstance(body["last_loop"], str)


def test_list_endpoint_has_no_internal_items():
    unknowns, _ = _parse_unknowns()
    internal_ids = {u["id"] for u in unknowns if u["category"] in INTERNAL_UNKNOWN_CATEGORIES}
    res = client.get("/api/public/unknowns?limit=200")
    assert res.status_code == 200
    items = res.json()
    returned_ids = {i["id"] for i in items}
    assert not (returned_ids & internal_ids), "internal unknowns leaked to public endpoint"
    for i in items:
        assert i["state"] in _UNKNOWN_STATES
        assert i["cheapest_test"], f"{i['id']} missing cheapest test"
        assert i["stake"], f"{i['id']} missing stake"


def test_list_endpoint_state_filter():
    res = client.get("/api/public/unknowns?state=SUPPORTED")
    assert res.status_code == 200
    for i in res.json():
        assert i["state"] == "SUPPORTED"


def test_list_endpoint_rejects_bad_state():
    res = client.get("/api/public/unknowns?state=MADE_UP")
    assert res.status_code == 400
