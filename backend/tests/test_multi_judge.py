from app import models
from app.services import evidence_graph, multi_judge
from app.services.observer_engine import ObserverEngine


def evidence_fixture(db, url="https://example.test/judgment"):
    signal = ObserverEngine(db).observe(
        "Small contractors lose hours manually scheduling repairs.",
        source="rss",
        metadata={"url": url, "external_id": url.rsplit("/", 1)[-1]},
    )
    return db.query(models.Evidence).filter_by(signal_id=signal.id).one()


def positive_judge(question, evidence):
    return {
        "label": "positive",
        "conclusion": "The evidence supports recurring customer pain.",
        "reasoning": "The source describes repeated manual work.",
        "uncertainty": "Pricing remains unknown.",
        "confidence": 0.8,
    }


def negative_judge(question, evidence):
    return {
        "label": "negative",
        "conclusion": "The evidence does not establish willingness to pay.",
        "reasoning": "No purchase or pricing evidence is present.",
        "uncertainty": "More pricing evidence is required.",
    }


def spec(name, evaluate, available=lambda: True):
    return multi_judge.JudgeSpec(
        name=name,
        provider="test-provider",
        model=f"{name}-model",
        evaluate=evaluate,
        available=available,
    )


def test_multiple_judges_preserve_identity_and_prevent_duplicate_work(db):
    evidence = evidence_fixture(db)
    judges = [spec("judge-a", positive_judge), spec("judge-b", negative_judge)]

    first = multi_judge.run_judgments(
        db,
        question="Does this evidence establish a monetizable problem?",
        evidence_ids=[evidence.id],
        judges=judges,
    )
    second = multi_judge.run_judgments(
        db,
        question="Does this evidence establish a monetizable problem?",
        evidence_ids=[evidence.id],
        judges=judges,
    )

    assert [item.provider for item in first] == ["test-provider", "test-provider"]
    assert [item.model for item in first] == ["judge-a-model", "judge-b-model"]
    assert first[0].confidence == 0.8
    assert first[1].confidence is None
    assert [item.id for item in second] == [item.id for item in first]
    assert db.query(models.Judgment).count() == 2
    assert db.query(models.EvidenceRelationship).filter_by(judgment_id=first[0].id).count() == 1


def test_agreement_and_disagreement_create_durable_comparisons(db):
    evidence = evidence_fixture(db)
    agreement_judgments = multi_judge.run_judgments(
        db,
        question="Is there recurring pain?",
        evidence_ids=[evidence.id],
        judges=[spec("a1", positive_judge), spec("a2", positive_judge)],
    )
    agreement = multi_judge.compare_judgments(
        db,
        question="Is there recurring pain?",
        judgment_ids=[item.id for item in agreement_judgments],
        evidence_ids=[evidence.id],
    )
    assert agreement.outcome == "agreement"
    assert agreement.follow_up_question_id is None

    disagreement_judgments = multi_judge.run_judgments(
        db,
        question="Will customers pay?",
        evidence_ids=[evidence.id],
        judges=[spec("b1", positive_judge), spec("b2", negative_judge)],
    )
    disagreement = multi_judge.compare_judgments(
        db,
        question="Will customers pay?",
        judgment_ids=[item.id for item in disagreement_judgments],
        evidence_ids=[evidence.id],
    )

    assert disagreement.outcome == "disagreement"
    assert disagreement.follow_up_question_id is not None
    follow_up = db.get(models.ResearchQuestion, disagreement.follow_up_question_id)
    assert follow_up.question == "Resolve disagreement about: Will customers pay?"
    assert db.query(models.ResearchTask).filter_by(question_id=follow_up.id).count() >= 1


def test_failed_judge_missing_evidence_and_contradiction_are_preserved(db):
    evidence = evidence_fixture(db)
    failed = multi_judge.run_judgments(
        db,
        question="Can this claim be verified?",
        evidence_ids=[evidence.id],
        judges=[spec("unavailable", positive_judge, available=lambda: False)],
    )[0]
    comparison = multi_judge.compare_judgments(
        db,
        question="Can this claim be verified?",
        judgment_ids=[failed.id],
        evidence_ids=[evidence.id],
    )
    assert failed.status == "failed"
    assert failed.error
    assert comparison.outcome == "missing_evidence"

    claim, _ = evidence_graph.create_or_get_claim(db, "Contractors have a recurring scheduling problem.")
    evidence_graph.link_evidence(db, evidence, claim=claim, relation_type="contradicts")
    good = multi_judge.run_judgments(
        db,
        question="Is the claim supported?",
        evidence_ids=[evidence.id],
        judges=[spec("good", positive_judge), spec("good2", negative_judge)],
        claim_id=claim.id,
    )
    contradictory = multi_judge.compare_judgments(
        db,
        question="Is the claim supported?",
        judgment_ids=[item.id for item in good],
        evidence_ids=[evidence.id],
        claim_id=claim.id,
    )
    assert contradictory.outcome == "disagreement"
    assert contradictory.contradictory_claims
    assert db.get(models.Claim, claim.id).epistemic_state == "contested"


def test_new_evidence_allows_rejudgment_with_new_work_key(db):
    first = evidence_fixture(db, "https://example.test/judgment-1")
    second = evidence_fixture(db, "https://example.test/judgment-2")
    judge = spec("repeatable", positive_judge)

    first_run = multi_judge.run_judgments(
        db,
        question="Does the problem recur?",
        evidence_ids=[first.id],
        judges=[judge],
    )
    second_run = multi_judge.run_judgments(
        db,
        question="Does the problem recur?",
        evidence_ids=[first.id, second.id],
        judges=[judge],
    )

    assert first_run[0].id != second_run[0].id
    assert db.query(models.Judgment).count() == 2
    assert second_run[0].evidence_ids == f"{first.id},{second.id}"
