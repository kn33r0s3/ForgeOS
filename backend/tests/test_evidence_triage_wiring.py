from app.api import evidence_triage


def test_missing_endpoint_fails_closed_in_all_runtimes(monkeypatch):
    monkeypatch.delenv("EVIDENCE_TRIAGE_URL", raising=False)

    assert evidence_triage._triage_service_url() is None


def test_explicit_triage_endpoint_overrides_runtime_and_trims_slash(monkeypatch):
    monkeypatch.setenv("EVIDENCE_TRIAGE_URL", " https://triage.example/base/ ")
    assert evidence_triage._triage_service_url() == "https://triage.example/base"
