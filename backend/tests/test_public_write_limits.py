import asyncio

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.database import get_db
from app.main import app, invalid_input
from app.request_limits import _is_limited_write
from app.services.forge_bot_privacy import consume_rate_limited_request


def _visitor_request(path="/public/domain/1/close"):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("198.51.100.17", 12345),
            "server": ("testserver", 80),
        }
    )


@pytest.fixture
def client_for_db(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize(
    "path",
    [
        "/public/domain",
        "/public/domain/1/close",
        "/public/domain/1/dispute",
        "/public/domain/1/connections/2/response",
        "/public/booking-requests",
        "/signals/public-request",
        "/analyze",
        "/api/public/domain",
        "/api/public/domain/1/close",
        "/api/public/domain/1/dispute",
        "/api/public/domain/1/connections/2/response",
        "/api/public/booking-requests",
        "/api/signals/public-request",
        "/api/analyze",
    ],
)
def test_selected_public_posts_have_body_caps(path):
    assert _is_limited_write("POST", path)


def test_non_target_request_is_not_body_capped():
    assert not _is_limited_write("POST", "/public/feed")
    assert not _is_limited_write("GET", "/public/domain")


def test_api_domain_post_is_limited_to_five_per_visitor_per_hour(
    client_for_db,
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-only-rate-key")
    payload = {
        "kind": "job",
        "title": "TEST request",
        "detail": "TEST-only rate limit fixture",
    }

    responses = [
        client_for_db.post("/api/public/domain", json=payload)
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [200] * 5 + [429]
    assert responses[-1].json() == {
        "detail": "Hourly limit reached: no more than 5 requests per visitor per hour."
    }
    bucket = db.query(models.ForgeBotIntakeRateLimit).one()
    assert bucket.request_count == 6
    assert len(bucket.visitor_hash) == 64
    assert "testclient" not in bucket.visitor_hash
    assert db.query(models.DomainRecord).count() == 5


def test_domain_controls_are_limited_to_twenty_per_visitor_per_hour(
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-only-rate-key")
    request = _visitor_request()

    allowed = [
        consume_rate_limited_request(
            db,
            request,
            hmac_key=settings.FORGE_BOT_CONTACT_HMAC_KEY,
            scope="public-domain-control",
            limit=20,
        )
        for _ in range(21)
    ]

    assert allowed == [True] * 20 + [False]
    bucket = db.query(models.ForgeBotIntakeRateLimit).one()
    assert bucket.request_count == 21
    assert "198.51.100.17" not in bucket.visitor_hash


def test_public_demand_requests_are_limited_to_five_per_visitor_per_hour(
    client_for_db,
    db,
    monkeypatch,
):
    from app.services import worker_manager

    monkeypatch.setattr(settings, "FORGE_BOT_CONTACT_HMAC_KEY", "test-only-rate-key")
    monkeypatch.setattr(settings, "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", True)
    monkeypatch.setattr(worker_manager, "process_demand_task_in_background", lambda _: None)

    responses = [
        client_for_db.post(
            "/api/signals/public-request",
            json={"content": f"TEST ONLY demand request {index}"},
            headers={"Idempotency-Key": f"rate-limit-fixture-{index}"},
        )
        for index in range(6)
    ]

    assert [response.status_code for response in responses] == [202] * 5 + [429]
    assert responses[-1].json() == {
        "detail": "Hourly limit reached: no more than 5 requests per visitor per hour."
    }
    bucket = db.query(models.ForgeBotIntakeRateLimit).one()
    assert bucket.request_count == 6
    assert len(bucket.visitor_hash) == 64
    assert db.query(models.Signal).filter_by(source="user_request").count() == 5


def test_value_error_response_does_not_echo_submitted_values():
    submitted_value = "private-value@example.test"

    response = asyncio.run(
        invalid_input(_visitor_request(), ValueError(submitted_value))
    )

    assert response.status_code == 422
    assert response.body == b'{"detail":"Invalid request value."}'
    assert submitted_value.encode() not in response.body


@pytest.mark.parametrize(
    "path",
    [
        "/api/public/domain",
        "/api/public/domain/1/close",
        "/api/public/domain/1/dispute",
        "/api/public/domain/1/connections/2/response",
        "/api/public/booking-requests",
        "/api/signals/public-request",
        "/api/analyze",
    ],
)
def test_selected_public_posts_reject_bodies_over_16_kb(client_for_db, path):
    response = client_for_db.post(path, content=b"x" * (16 * 1024 + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body must be 16 KB or smaller."}
