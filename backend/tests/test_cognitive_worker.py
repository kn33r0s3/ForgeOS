import json

import pytest

from app import models
from app.config import settings
from app.services import cognitive_provider, cognitive_worker
from app.services import research_task_engine
from app.services.worker_manager import process_worker_task_by_id


class ReplacementProvider:
    name = "replacement-test"
    version = "test-v1"
    mode = "TEST"

    def __init__(self, proposals=None):
        self.context = None
        self.proposals = proposals

    def propose(self, context):
        self.context = context
        if self.proposals is not None:
            return self.proposals
        return [
            {
                "kind": "research_follow_up",
                "title": "Review the unresolved question",
                "rationale": "A test provider proposes review without asserting a finding.",
                "next_step": "Select a cleared source for owner review.",
                "evidence_ids": [],
            }
        ]


def make_research_task(db, objective="What evidence answers this research question?"):
    question = models.ResearchQuestion(question=objective)
    db.add(question)
    db.commit()
    db.refresh(question)
    return research_task_engine.create_task(
        db,
        question_id=question.id,
        source="test",
        query=objective,
        objective=objective,
    )


def test_worker_dispatch_uses_replaceable_provider_and_records_provenance(db, monkeypatch):
    research_task = make_research_task(db)
    evidence_rows = [
        models.Evidence(source="TEST", content=f"test-only evidence {index}")
        for index in range(cognitive_provider.MAX_COGNITIVE_EVIDENCE_IDS + 1)
    ]
    db.add_all(evidence_rows)
    db.flush()
    original_evidence_ids = [row.id for row in evidence_rows]
    research_task.evidence_ids = ",".join(map(str, original_evidence_ids))
    db.commit()

    replacement = ReplacementProvider()
    monkeypatch.setattr(
        cognitive_provider,
        "get_cognitive_provider",
        lambda: replacement,
    )
    worker_task = cognitive_worker.create_cognitive_task(db, research_task.id)
    worker_task_id = worker_task.id
    db.commit()
    assert cognitive_worker.create_cognitive_task(db, research_task.id).id == worker_task_id

    assert process_worker_task_by_id(db, worker_task_id, worker_type="cognitive") is True

    db.refresh(worker_task)
    db.refresh(research_task)
    assert worker_task.status == "completed"
    assert worker_task.outputs["status"] == "PROPOSED"
    assert worker_task.outputs["execution_allowed"] is False
    assert worker_task.outputs["provenance"]["provider"] == "replacement-test"
    assert worker_task.outputs["provenance"]["provider_mode"] == "TEST"
    assert worker_task.outputs["provenance"]["proposal_classification"] == "HYPOTHESIS"
    assert replacement.context.max_proposals == cognitive_provider.MAX_COGNITIVE_PROPOSALS
    assert len(replacement.context.evidence_ids) == cognitive_provider.MAX_COGNITIVE_EVIDENCE_IDS
    assert replacement.context.evidence_refs_truncated is True
    assert research_task.status == "planned"
    assert research_task.evidence_ids == ",".join(map(str, original_evidence_ids))
    assert db.query(models.Evidence).count() == len(original_evidence_ids)
    assert db.query(models.Action).count() == 0

    event = (
        db.query(models.WorldEvent)
        .filter_by(
            event_type="cognitive_proposals_generated",
            source="cognitive_worker",
            idempotency_key=f"cognitive-worker-proposals:v1:{worker_task_id}",
        )
        .one()
    )
    payload = json.loads(event.payload)
    assert payload["worker_task_id"] == worker_task_id
    assert payload["research_task_id"] == research_task.id
    assert payload["provider"] == "replacement-test"
    assert payload["context_sha256"]
    assert len(payload["proposal_sha256"]) == 1
    assert (
        db.query(models.ResearchTaskEvent)
        .filter_by(task_id=research_task.id, event_type="cognitive_proposals_generated")
        .count()
        == 1
    )


def test_default_mock_provider_produces_only_a_proposal(db, monkeypatch):
    monkeypatch.setattr(settings, "COGNITIVE_PROVIDER", "mock")
    research_task = make_research_task(db)
    worker_task = cognitive_worker.create_cognitive_task(db, research_task.id)
    db.commit()

    assert process_worker_task_by_id(db, worker_task.id, worker_type="cognitive") is True

    db.refresh(worker_task)
    assert worker_task.status == "completed"
    assert worker_task.outputs["provenance"]["provider"] == "mock"
    assert worker_task.outputs["provenance"]["provider_mode"] == "MOCK"
    assert worker_task.outputs["proposals"][0]["status"] == "PROPOSED"
    assert worker_task.outputs["proposals"][0]["execution_authorized"] is False
    assert db.query(models.Evidence).count() == 0
    assert db.query(models.Action).count() == 0


def test_unavailable_provider_fails_closed_and_records_research_event(db, monkeypatch):
    research_task = make_research_task(db)
    worker_task = cognitive_worker.create_cognitive_task(db, research_task.id)
    monkeypatch.setattr(settings, "COGNITIVE_PROVIDER", "gemini")

    assert process_worker_task_by_id(db, worker_task.id, worker_type="cognitive") is True

    db.refresh(worker_task)
    assert worker_task.status == "queued"
    assert worker_task.attempts == 1
    assert "GEMINI_API_KEY" in worker_task.error
    assert db.query(models.WorldEvent).filter_by(source="cognitive_worker").count() == 0
    failed_event = (
        db.query(models.ResearchTaskEvent)
        .filter_by(task_id=research_task.id, event_type="cognitive_provider_unavailable")
        .one()
    )
    assert failed_event.details["provider"] == "gemini"
    assert failed_event.details["error_code"] == "provider_unavailable"


def test_cognitive_objective_bound_is_enforced_before_provider_call(db):
    research_task = make_research_task(
        db,
        objective="x" * (cognitive_provider.MAX_COGNITIVE_OBJECTIVE_CHARS + 1),
    )
    worker_task = cognitive_worker.create_cognitive_task(db, research_task.id)
    replacement = ReplacementProvider()

    with pytest.raises(cognitive_provider.CognitiveTaskBoundsError):
        cognitive_worker.run_cognitive_task(db, worker_task, provider=replacement)

    assert replacement.context is None
    assert db.query(models.WorldEvent).filter_by(source="cognitive_worker").count() == 0


def test_proposals_over_limit_are_rejected(db):
    research_task = make_research_task(db)
    worker_task = cognitive_worker.create_cognitive_task(db, research_task.id)
    context = cognitive_provider.CognitiveTaskContext(
        research_task_id=research_task.id,
        objective=research_task.objective,
        evidence_ids=(),
        evidence_refs_truncated=False,
    )
    one_proposal = ReplacementProvider().propose(context)[0]
    provider = ReplacementProvider(
        proposals=[one_proposal] * (cognitive_provider.MAX_COGNITIVE_PROPOSALS + 1)
    )

    with pytest.raises(cognitive_provider.CognitiveProposalValidationError, match="between one"):
        cognitive_worker.run_cognitive_task(db, worker_task, provider=provider)

    assert db.query(models.WorldEvent).filter_by(source="cognitive_worker").count() == 0
    assert (
        db.query(models.ResearchTaskEvent)
        .filter_by(task_id=research_task.id, event_type="cognitive_proposal_rejected")
        .count()
        == 1
    )


@pytest.mark.parametrize(
    "change",
    [
        {"execution_authorized": True},
        {"action_type": "send_email"},
        {"evidence_ids": [999]},
    ],
)
def test_proposal_schema_rejects_execution_or_unlinked_evidence(db, change):
    research_task = make_research_task(db)
    worker_task = cognitive_worker.create_cognitive_task(db, research_task.id)
    context = cognitive_provider.CognitiveTaskContext(
        research_task_id=research_task.id,
        objective=research_task.objective,
        evidence_ids=(),
        evidence_refs_truncated=False,
    )
    proposal = ReplacementProvider().propose(context)[0]
    proposal.update(change)

    with pytest.raises(cognitive_provider.CognitiveProposalValidationError):
        cognitive_worker.run_cognitive_task(
            db,
            worker_task,
            provider=ReplacementProvider(proposals=[proposal]),
        )

    assert db.query(models.Action).count() == 0
    assert db.query(models.WorldEvent).filter_by(source="cognitive_worker").count() == 0
