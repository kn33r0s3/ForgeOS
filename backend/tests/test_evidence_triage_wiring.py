from app.api import evidence_triage


def test_deployed_runtime_does_not_fall_back_to_compose_only_hostname(monkeypatch):
    monkeypatch.delenv("EVIDENCE_TRIAGE_URL", raising=False)
    monkeypatch.setattr(evidence_triage.security, "_deployed_runtime", lambda: True)

    assert evidence_triage._triage_service_url() is None


def test_local_runtime_uses_the_compose_service_default(monkeypatch):
    monkeypatch.delenv("EVIDENCE_TRIAGE_URL", raising=False)
    monkeypatch.setattr(evidence_triage.security, "_deployed_runtime", lambda: False)

    assert evidence_triage._triage_service_url() == "http://evidence-triage:8787"


def test_explicit_triage_endpoint_overrides_runtime_and_trims_slash(monkeypatch):
    monkeypatch.setenv("EVIDENCE_TRIAGE_URL", " https://triage.example/base/ ")
    monkeypatch.setattr(evidence_triage.security, "_deployed_runtime", lambda: True)

    assert evidence_triage._triage_service_url() == "https://triage.example/base"
