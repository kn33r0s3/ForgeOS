"""Renovation Phase 3: safety-net tests.

Health contract keys, settings gate, request-id header, PII log masking.
"""

import pytest
from fastapi.testclient import TestClient


def test_health_returns_contract_keys():
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    try:
        resp = client.get("/health")
    finally:
        client.close()
    assert resp.status_code == 200
    body = resp.json()
    # The four renovation contract keys...
    assert "ok" in body and isinstance(body["ok"], bool)
    assert "version" in body and body["version"]
    assert "time" in body and body["time"]
    assert body["db"] in ("up", "down", "not_configured")
    # ...alongside the pre-existing keys current consumers rely on.
    assert "status" in body and "ready" in body


def test_settings_missing_required_prints_clear_line(monkeypatch, capsys):
    from app.settings import check_required_env

    monkeypatch.delenv("RENOVATION_TEST_REQUIRED_XYZ", raising=False)
    with pytest.raises(SystemExit):
        check_required_env(["RENOVATION_TEST_REQUIRED_XYZ"])
    err = capsys.readouterr().err
    assert "Missing setting: RENOVATION_TEST_REQUIRED_XYZ" in err


def test_settings_all_present_starts_fine(monkeypatch):
    from app.settings import check_required_env

    monkeypatch.setenv("RENOVATION_TEST_REQUIRED_XYZ", "1")
    check_required_env(["RENOVATION_TEST_REQUIRED_XYZ"])  # must not raise


def test_settings_default_required_list_is_empty():
    # Honest: nothing is genuinely required for startup today (SQLite
    # fallback). The gate mechanism is real; the list stays empty until
    # something truly cannot start without it.
    from app import settings as app_settings

    assert app_settings.REQUIRED_ENV_VARS == []


def test_request_id_header_honored_and_minted():
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    try:
        honored = client.get("/health", headers={"X-Request-ID": "test-abc-123"})
        assert honored.headers["X-Request-ID"] == "test-abc-123"
        minted = client.get("/health")
        assert minted.headers.get("X-Request-ID")
        # Error responses carry the id too (traceability without changing
        # the established {"detail": ...} body contract).
        not_found = client.get("/no-such-route-renovation")
        assert not_found.status_code == 404
        assert not_found.headers.get("X-Request-ID")
    finally:
        client.close()


def test_pii_mask_filter():
    # Unit-test the filter object directly: CPython logger-level filters do
    # not apply to propagated records, so the app attaches PIIMaskFilter at
    # handler level (see _install_pii_filter). This proves the masking logic.
    import logging  # local: keeps the top of file free of test-only imports

    from app.main import PIIMaskFilter

    filt = PIIMaskFilter()
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "call 9841234567 or a@b.com", (), None
    )
    assert filt.filter(record) is True
    assert record.getMessage() == "call [phone] or [email]"

    # +977 prefix variant is masked too.
    record2 = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "sms +977-9851234567 now", (), None
    )
    assert filt.filter(record2) is True
    assert "9851234567" not in record2.getMessage()
