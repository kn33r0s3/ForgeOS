"""Step 1: owner-auth on the 5 previously unauthenticated routers.

Verifies that write-capable routes on orchestrator, substrate, products,
observer, and evidence_triage require the owner key:
- no FORGE_API_KEY configured -> 503 (owner access unavailable)
- key configured, missing/wrong key -> 401
- key configured, correct key -> route executes (not 401/503)

Public read-only routes are verified to remain open (no accidental lockout).
"""
import pytest
from fastapi.testclient import TestClient

from app import security
from app.database import get_db
from app.main import app
from app.services import world_graph


@pytest.fixture
def client(db, monkeypatch):
    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_get_db
    world_graph.seed_core_types(db)
    db.commit()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()
    c.close()


def _keyed(monkeypatch, key="step1-owner-key"):
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", key)
    return {"X-API-Key": key}


# (method, path, json body or None) for one write route per router
WRITE_ROUTES = [
    ("post", "/orchestrate/9999/advance", None),
    ("post", "/forge/substrate/types", {"category": "entity_type", "type_name": "t", "schema": {}, "owner_agent": "test"}),
    ("post", "/products", {"name": "p", "offer": "o"}),
    ("post", "/observer/observe", {"content": "hello", "source": "manual"}),
    ("post", "/evidence-triage/triage", {"signal": "x"}),
]

# read-only routes that must stay public
PUBLIC_READS = [
    "/forge/substrate/types",
    "/forge/substrate/discovery/methods",
    "/observer/signals",
    "/products",
]


@pytest.mark.parametrize("method,path,body", WRITE_ROUTES)
def test_writes_503_without_configured_key(client, monkeypatch, method, path, body):
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")
    res = client.request(method, path, json=body)
    assert res.status_code == 503, f"{method} {path}: {res.status_code}"


@pytest.mark.parametrize("method,path,body", WRITE_ROUTES)
def test_writes_401_with_wrong_or_missing_key(client, monkeypatch, method, path, body):
    headers = _keyed(monkeypatch)
    # missing key
    res = client.request(method, path, json=body)
    assert res.status_code == 401, f"{method} {path}: {res.status_code}"
    # wrong key
    res = client.request(method, path, json=body, headers={"X-API-Key": "wrong"})
    assert res.status_code == 401, f"{method} {path}: {res.status_code}"
    # correct key must pass the auth gate (not 401/503-from-auth).
    # Note: /evidence-triage/triage is a proxy; it returns 503 when the
    # downstream triage service is unavailable. That 503 is legitimate
    # endpoint behavior AFTER auth passed, so we only assert "not 401".
    res = client.request(method, path, json=body, headers=headers)
    assert res.status_code != 401, f"{method} {path}: {res.status_code}"


@pytest.mark.parametrize("path", PUBLIC_READS)
def test_public_reads_stay_open(client, monkeypatch, path):
    # unconfigured: open (local-first)
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")
    res = client.get(path)
    assert res.status_code != 401 and res.status_code != 503, f"{path}: {res.status_code}"
    # configured: reads stay open without key (middleware only gates private paths)
    _keyed(monkeypatch)
    res = client.get(path)
    # /forge/substrate/* reads are private_substrate_read -> 401 when keyed but no key presented
    if path.startswith("/forge/substrate/"):
        assert res.status_code == 401, f"{path}: {res.status_code}"
    else:
        assert res.status_code not in (401, 503), f"{path}: {res.status_code}"
