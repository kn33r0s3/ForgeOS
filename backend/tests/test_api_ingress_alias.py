"""The deployed ingress only reaches `/api/*`, so the contract must answer there.

Vercel routes `/api/*` to the Python service and nothing else, so a route that
exists only at the service root is unreachable in production even though it
works locally. These tests pin the mirror that closes that gap, including the
schema document used by client generators and contract checks.
"""

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_root_routes_are_reachable_under_the_api_prefix(db):
    client = _client()

    assert client.get("/health").status_code == 200
    mirrored = client.get("/api/health")

    assert mirrored.status_code == 200
    assert mirrored.json()["status"] == "ok"


def test_openapi_contract_is_reachable_under_the_api_prefix(db):
    client = _client()

    schema = client.get("/api/openapi.json")

    assert schema.status_code == 200
    payload = schema.json()
    assert payload["info"]["title"] == "Hami"
    assert "/health" in payload["paths"]


def test_openapi_alias_matches_the_root_document(db):
    client = _client()

    root = client.get("/openapi.json").json()
    mirrored = client.get("/api/openapi.json").json()

    assert mirrored == root


def test_api_prefix_routes_stay_out_of_the_published_schema(db):
    client = _client()

    paths = client.get("/api/openapi.json").json()["paths"]

    assert not any(path.startswith("/api/") for path in paths)
