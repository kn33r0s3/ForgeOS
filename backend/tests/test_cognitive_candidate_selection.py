from app import models
from app.config import settings
from app.services import cognitive_provider, cognitive_worker, research_task_engine


class _ProposalProvider:
    name = "candidate-selection-test"
    version = "test-v1"
    mode = "TEST"
    last_call_metadata = {}

    def __init__(self):
        self.context = None

    def propose(self, context):
        self.context = context
        return [{
            "kind": "research_follow_up",
            "title": "Verify the open question",
            "rationale": "A source claim is a lead, not independent verification.",
            "next_step": "Compare with another permitted source.",
            "evidence_ids": list(context.available_evidence_ids),
            "status": "PROPOSED",
            "execution_authorized": False,
        }]


def _completed_research_with_evidence(db, *, objective, collection_status="collected", source_type="third_party", consent_status="not_required"):
    question = models.ResearchQuestion(question=objective, priority_score=100)
    db.add(question)
    db.commit()
    db.refresh(question)

    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="test",
        query=objective,
        objective=objective,
    )
    task.status = "completed"
    evidence = models.Evidence(
        source="candidate-selection-test",
        title="Public evidence candidate",
        claim="A bounded claim needing independent confirmation.",
        canonical_url="https://example.gov.np/candidate",
        source_kind="REAL",
        source_type=source_type,
        consent_status=consent_status,
        collection_status=collection_status,
    )
    db.add(evidence)
    db.flush()
    task.evidence_ids = str(evidence.id)
    db.commit()
    return task, evidence


def _enable_test_provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "COGNITIVE_PROVIDER", "ollama")
    monkeypatch.delenv("VERCEL", raising=False)
    from app.services import operating_v4

    monkeypatch.setattr(operating_v4, "check_agent_run_allowed", lambda _db: None)
    provider = _ProposalProvider()
    monkeypatch.setattr(cognitive_provider, "get_cognitive_provider", lambda: provider)
    return provider


def test_completed_worker_task_does_not_consume_candidate_limit(db, monkeypatch):
    previously_completed, _old_evidence = _completed_research_with_evidence(
        db, objective="Older research already has a completed cognitive result"
    )
    old_worker = cognitive_worker.create_cognitive_task(db, previously_completed.id)
    old_worker.status = "completed"
    old_worker.outputs = {"status": "PROPOSED", "execution_allowed": False}
    db.commit()

    eligible, _new_evidence = _completed_research_with_evidence(
        db, objective="A new research question still needs a proposal"
    )
    provider = _enable_test_provider(monkeypatch)

    result = cognitive_worker.run_pending_cognitive_tasks(
        db, limit=1, candidate_limit=1
    )

    assert result["completed"] == 1
    assert result["outcomes"][0]["research_task_id"] == eligible.id
    assert old_worker.status == "completed"
    assert provider.context is not None
    assert provider.context.available_evidence_ids


def test_non_collected_public_evidence_does_not_consume_candidate_limit(db, monkeypatch):
    rejected, rejected_evidence = _completed_research_with_evidence(
        db,
        objective="An older public-looking source failed collection validation",
        collection_status="rejected",
    )
    eligible, collected_evidence = _completed_research_with_evidence(
        db,
        objective="A later source was collected successfully",
        collection_status="collected",
    )
    provider = _enable_test_provider(monkeypatch)

    result = cognitive_worker.run_pending_cognitive_tasks(
        db, limit=1, candidate_limit=1
    )

    assert result["completed"] == 1
    assert result["outcomes"][0]["research_task_id"] == eligible.id
    assert collected_evidence.id in provider.context.available_evidence_ids
    assert rejected_evidence.id not in provider.context.available_evidence_ids
    assert db.query(models.WorkerTask).filter_by(
        idempotency_key=f"cognitive-research-task:v1:{rejected.id}"
    ).count() == 0
