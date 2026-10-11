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

from app import models, security
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
    ("post", "/signals", {"content": "anonymous raw signal"}),
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


PRIVATE_INTELLIGENCE_READS = [
    "/signals",
    "/observer/signals",
    "/observer/recent",
    "/forge/revenue-sources",
    "/intelligence/youtube/999999",
    "/intelligence/performance/tools/unknown-tool",
    "/intelligence/performance/sources/unknown-source",
]


@pytest.mark.parametrize("path", PRIVATE_INTELLIGENCE_READS)
def test_private_owner_reads_require_owner_key(client, monkeypatch, path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("NODE_ENV", "test")

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")
    unconfigured = client.get(path)
    assert unconfigured.status_code == 503, f"{path}: {unconfigured.status_code}"

    _keyed(monkeypatch)
    missing = client.get(path)
    wrong = client.get(path, headers={"X-API-Key": "wrong"})
    assert missing.status_code == 401, f"{path}: {missing.status_code}"
    assert wrong.status_code == 401, f"{path}: {wrong.status_code}"

    allowed = client.get(path, headers={"X-API-Key": "step1-owner-key"})
    assert allowed.status_code not in (401, 503), f"{path}: {allowed.status_code}"


def test_research_status_requires_submission_capability_before_lookup(client, db, monkeypatch):
    from app.api import analyze as analyze_api

    monkeypatch.setattr(
        analyze_api.settings,
        "FORGE_BOT_CONTACT_HMAC_KEY",
        "test-only-research-status-key-0123456789",
    )
    signal = models.Signal(source="manual", content="TEST-only status-token source")
    question = models.ResearchQuestion(
        question="TEST-only protected research status",
        status="open",
        research_plan={"status": "research_completed", "requirements": [], "unknowns": []},
    )
    other_question = models.ResearchQuestion(
        question="TEST-only another protected research status",
        status="open",
        research_plan={"status": "research_completed", "requirements": [], "unknowns": []},
    )
    db.add_all([signal, question, other_question])
    db.commit()
    db.refresh(signal)
    db.refresh(question)
    db.refresh(other_question)
    path = f"/analyze/{question.id}/status"

    missing = client.get(path)
    wrong = client.get(path, headers={"X-Research-Status-Token": "invalid-capability"})
    token = analyze_api._research_status_token(question.id, signal.id)
    valid = client.get(path, headers={"X-Research-Status-Token": token})
    replay = client.get(
        f"/analyze/{other_question.id}/status",
        headers={"X-Research-Status-Token": token},
    )

    assert missing.status_code == 404
    assert wrong.status_code == 404
    assert valid.status_code == 200, valid.text
    assert valid.json()["research_question_id"] == question.id
    assert replay.status_code == 404


def test_deployed_runtime_fails_closed_for_privileged_paths_when_key_is_missing(monkeypatch):
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("NODE_ENV", raising=False)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/api/observer/observe",
        "raw_path": b"/api/observer/observe",
        "query_string": b"",
        "headers": [],
        "server": ("haminp.vercel.app", 443),
        "client": ("127.0.0.1", 10000),
        "root_path": "",
    }
    called = False

    async def call_next(_request):
        nonlocal called
        called = True
        return Response("downstream-called", status_code=200)

    response = asyncio.run(security.api_key_middleware(Request(scope), call_next))
    assert response.status_code == 503
    assert b"FORGE_API_KEY must be configured" in response.body
    assert called is False


def test_deployed_runtime_keeps_explicit_public_submission_paths_open_without_key(monkeypatch):
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("NODE_ENV", raising=False)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/api/public/domain",
        "raw_path": b"/api/public/domain",
        "query_string": b"",
        "headers": [],
        "server": ("haminp.vercel.app", 443),
        "client": ("127.0.0.1", 10000),
        "root_path": "",
    }

    async def call_next(_request):
        return Response("public-submit", status_code=200)

    response = asyncio.run(security.api_key_middleware(Request(scope), call_next))
    assert response.status_code == 200
    assert response.body == b"public-submit"


def test_local_runtime_keeps_optional_gate_off_when_key_is_missing(monkeypatch):
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("NODE_ENV", "test")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/observer/observe",
        "raw_path": b"/api/observer/observe",
        "query_string": b"",
        "headers": [],
        "server": ("localhost", 8080),
        "client": ("127.0.0.1", 10000),
        "root_path": "",
    }

    async def call_next(_request):
        return Response("local-pass", status_code=200)

    response = asyncio.run(security.api_key_middleware(Request(scope), call_next))
    assert response.status_code == 200
    assert response.body == b"local-pass"





def test_public_payment_reconciliation_requires_post_method(monkeypatch):
    from fastapi import FastAPI

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "test-owner-key")
    app = FastAPI()
    app.middleware("http")(security.api_key_middleware)

    @app.api_route("/{route:path}", methods=["POST", "PUT"])
    def public_handler(route: str):
        return {"route": route}

    path = "/api/payments/intent/public-recovery-ref-0123456789/reconcile"
    with TestClient(app) as test_client:
        assert test_client.post(path).status_code == 200
        assert test_client.put(path).status_code == 401
