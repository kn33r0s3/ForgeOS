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
    claim, _ = evidence_graph.create_or_get_claim(
        db,
        "Customers will pay for the service.",
    )
    disagreement = multi_judge.compare_judgments(
        db,
        question="Will customers pay?",
        judgment_ids=[item.id for item in disagreement_judgments],
        evidence_ids=[evidence.id],
        claim_id=claim.id,
    )

    assert disagreement.outcome == "disagreement"
    assert disagreement.follow_up_question_id is not None
    follow_up = db.get(models.ResearchQuestion, disagreement.follow_up_question_id)
    assert follow_up.question == "Resolve disagreement about: Will customers pay?"
    assert follow_up.source_claim_id == claim.id
    assert db.query(models.ResearchTask).filter_by(question_id=follow_up.id).count() >= 1


def test_failed_judge_is_evaluation_incomplete_not_missing_evidence(db):
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
    assert comparison.outcome == "evaluation_incomplete"
    assert comparison.missing_evidence == []
    # The data exists; the judge failed. Fix evaluation availability instead
    # of spawning a new evidence-search question from an infrastructure fault.
    assert comparison.follow_up_question_id is None
    assert db.query(models.ResearchQuestion).count() == 0

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


def test_unavailable_judge_retries_after_availability_recovers_without_erasing_failure(db):
    evidence = evidence_fixture(db)
    availability = {"ready": False}
    judge = spec(
        "recovering-judge",
        positive_judge,
        available=lambda: availability["ready"],
    )
    kwargs = {
        "question": "Does this evidence establish recurring pain?",
        "evidence_ids": [evidence.id],
        "judges": [judge],
    }

    first = multi_judge.run_judgments(db, **kwargs)[0]
    assert first.status == "failed"
    assert first.error.startswith("judge unavailable:")

    repeated_while_unavailable = multi_judge.run_judgments(db, **kwargs)[0]
    assert repeated_while_unavailable.id == first.id
    assert db.query(models.Judgment).count() == 1

    availability["ready"] = True
    recovered = multi_judge.run_judgments(db, **kwargs)[0]
    assert recovered.status == "completed"
    assert recovered.id != first.id
    assert recovered.judgment_key == first.judgment_key
    assert first.status == "failed"  # historical failure remains intact
    assert db.query(models.Judgment).count() == 2

    repeated_after_recovery = multi_judge.run_judgments(db, **kwargs)[0]
    assert repeated_after_recovery.id == recovered.id
    assert db.query(models.Judgment).count() == 2


def test_openai_judge_remains_blocked_even_when_flag_and_key_are_configured(monkeypatch):
    from app.config import settings

    requested = []

    class FakeRegistry:
        def get(self, name):
            requested.append(name)
            raise KeyError(name)

    monkeypatch.setattr(multi_judge, "default_registry", lambda: FakeRegistry())
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "configured-for-test")
    monkeypatch.setattr(settings, "FORGEOS_OPENAI_JUDGE_ENABLED", False)
    assert multi_judge._default_judges() == []
    assert requested == ["local-qwen3-coder"]

    requested.clear()
    # The legacy switch is not a spend-control system; it cannot override the
    # centralized block until real usage metering is connected to the global cap.
    monkeypatch.setattr(settings, "FORGEOS_OPENAI_JUDGE_ENABLED", True)
    assert multi_judge._default_judges() == []
    assert requested == ["local-qwen3-coder"]


def test_no_available_judges_does_not_create_recursive_research_questions(db):
    evidence = evidence_fixture(db)
    judgments = multi_judge.run_judgments(
        db,
        question="Does this publication establish customer demand?",
        evidence_ids=[evidence.id],
        judges=[],
    )

    comparison = multi_judge.compare_judgments(
        db,
        question="Does this publication establish customer demand?",
        judgment_ids=[item.id for item in judgments],
        evidence_ids=[evidence.id],
    )

    assert judgments == []
    assert comparison.outcome == "evaluation_incomplete"
    assert comparison.missing_evidence == []
    assert comparison.follow_up_question_id is None
    assert db.query(models.ResearchQuestion).count() == 0


def test_one_distinct_model_cannot_create_agreement(db):
    evidence = evidence_fixture(db)
    judgment = multi_judge.run_judgments(
        db,
        question="Does this evidence establish recurring pain?",
        evidence_ids=[evidence.id],
        judges=[spec("solo", positive_judge)],
    )[0]

    comparison = multi_judge.compare_judgments(
        db,
        question="Does this evidence establish recurring pain?",
        judgment_ids=[judgment.id],
        evidence_ids=[evidence.id],
    )

    assert judgment.status == "completed"
    assert comparison.outcome == "insufficient_judges"
    assert "single-model assessment" in comparison.summary
    assert comparison.follow_up_question_id is None
    assert db.query(models.ResearchQuestion).count() == 0


def test_missing_evidence_state_requires_an_absent_referenced_row(db):
    missing_id = 987654321
    judgment = models.Judgment(
        judge_name="fixture-judge",
        provider="fixture-provider",
        model="fixture-model",
        question="Does the referenced evidence exist?",
        conclusion="A row is referenced but absent.",
        reasoning_summary="The record must be found before it can be judged.",
        conclusion_label="positive",
        evidence_ids=str(missing_id),
        status="completed",
        judgment_key="missing-evidence-row-fixture",
    )
    db.add(judgment)
    db.commit()
    db.refresh(judgment)

    comparison = multi_judge.compare_judgments(
        db,
        question="Does the referenced evidence exist?",
        judgment_ids=[judgment.id],
        evidence_ids=[missing_id],
    )

    assert comparison.outcome == "missing_evidence"
    assert comparison.missing_evidence == [missing_id]
    assert comparison.follow_up_question_id is not None


def test_judgment_for_another_evidence_set_is_not_compared(db):
    first = evidence_fixture(db, "https://example.test/judgment-context-1")
    second = evidence_fixture(db, "https://example.test/judgment-context-2")
    judgment = multi_judge.run_judgments(
        db,
        question="Does this evidence establish recurring pain?",
        evidence_ids=[first.id],
        judges=[spec("context", positive_judge)],
    )[0]

    comparison = multi_judge.compare_judgments(
        db,
        question="Does this evidence establish recurring pain?",
        judgment_ids=[judgment.id],
        evidence_ids=[second.id],
    )

    assert comparison.outcome == "evaluation_incomplete"
    assert "different question or evidence set" in comparison.summary
    assert comparison.follow_up_question_id is None


def test_unstructured_model_text_cannot_become_a_positive_or_negative_verdict():
    result = multi_judge._normalize_result(
        "The evidence does not establish demand; a likely explanation is missing data."
    )
    explicit = multi_judge._normalize_result({
        "label": "POSITIVE",
        "conclusion": "The source directly documents the claimed event.",
        "confidence": 1.7,
    })

    assert result["conclusion_label"] == "uncertain"
    assert explicit["conclusion_label"] == "positive"
    assert explicit["confidence"] is None



def test_new_contract_versions_do_not_reuse_legacy_judgment_or_comparison_cache(db):
    import hashlib
    import json

    evidence = evidence_fixture(db)
    question = "Does this evidence support the exact claim?"
    judge = spec(
        "legacy-cache-judge",
        lambda _question, _evidence: "The evidence is unlikely to support this claim.",
    )

    legacy_judgment_payload = {
        "judge": judge.name,
        "provider": judge.provider,
        "model": judge.model,
        "question": question.strip(),
        "evidence_ids": [evidence.id],
        "claim_id": None,
        "opportunity_id": None,
    }
    legacy_judgment_key = hashlib.sha256(
        json.dumps(legacy_judgment_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    old_judgment = models.Judgment(
        judge_name=judge.name,
        provider=judge.provider,
        model=judge.model,
        question=question,
        conclusion="The evidence is unlikely to support this claim.",
        reasoning_summary="Legacy keyword inference was not a validated verdict.",
        conclusion_label="positive",
        evidence_ids=str(evidence.id),
        uncertainty="Legacy cached result",
        confidence=None,
        status="completed",
        judgment_key=legacy_judgment_key,
    )
    db.add(old_judgment)
    db.commit()
    db.refresh(old_judgment)

    fresh_judgments = multi_judge.run_judgments(
        db,
        question=question,
        evidence_ids=[evidence.id],
        judges=[judge],
    )
    fresh = fresh_judgments[0]
    assert fresh.id != old_judgment.id
    assert fresh.judgment_key != old_judgment.judgment_key
    assert fresh.conclusion_label == "uncertain"

    # Simulate a legacy cached comparison for the new judgment IDs. Current
    # comparison rules must not return it just because the request is repeated.
    legacy_comparison_payload = {
        "question": question,
        "judgments": [fresh.id],
        "evidence": [evidence.id],
        "claim_id": None,
    }
    legacy_comparison_key = hashlib.sha256(
        json.dumps(legacy_comparison_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    old_comparison = models.JudgmentComparison(
        question=question,
        judgment_ids=[fresh.id],
        evidence_ids=str(evidence.id),
        outcome="agreement",
        summary="Legacy cached singleton agreement is invalid under the current contract.",
        disagreement_points=[],
        missing_evidence=[],
        contradictory_claims=[],
        unsupported_conclusions=[],
        comparison_key=legacy_comparison_key,
    )
    db.add(old_comparison)
    db.commit()
    db.refresh(old_comparison)

    legacy_judgment_comparison = multi_judge.compare_judgments(
        db,
        question=question,
        judgment_ids=[old_judgment.id],
        evidence_ids=[evidence.id],
    )
    assert legacy_judgment_comparison.outcome == "evaluation_incomplete"
    assert "older evaluation contract" in legacy_judgment_comparison.summary
    assert legacy_judgment_comparison.follow_up_question_id is None

    comparison = multi_judge.compare_judgments(
        db,
        question=question,
        judgment_ids=[fresh.id],
        evidence_ids=[evidence.id],
    )
    assert comparison.id != old_comparison.id
    assert comparison.outcome == "insufficient_judges"
    assert db.get(models.JudgmentComparison, old_comparison.id).outcome == "agreement"


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



def test_judgment_cache_is_scoped_to_claim_and_opportunity(db):
    evidence = evidence_fixture(db)
    claim_a, _ = evidence_graph.create_or_get_claim(db, "Claim A: recurring scheduling problem.")
    claim_b, _ = evidence_graph.create_or_get_claim(db, "Claim B: willingness to pay.")

    judge = spec("context-sensitive", positive_judge)
    judgment_a = multi_judge.run_judgments(
        db,
        question="Is the supplied proposition supported?",
        evidence_ids=[evidence.id],
        judges=[judge],
        claim_id=claim_a.id,
    )[0]
    judgment_a_repeat = multi_judge.run_judgments(
        db,
        question="Is the supplied proposition supported?",
        evidence_ids=[evidence.id],
        judges=[judge],
        claim_id=claim_a.id,
    )[0]
    judgment_b = multi_judge.run_judgments(
        db,
        question="Is the supplied proposition supported?",
        evidence_ids=[evidence.id],
        judges=[judge],
        claim_id=claim_b.id,
    )[0]

    assert judgment_a.id == judgment_a_repeat.id
    assert judgment_a.id != judgment_b.id
    assert judgment_a.claim_id == claim_a.id
    assert judgment_b.claim_id == claim_b.id

    opportunity_a_record = models.Opportunity(
        problem="Opportunity A: reduce scheduling overhead",
    )
    opportunity_b_record = models.Opportunity(
        problem="Opportunity B: validate willingness to pay",
    )
    db.add_all([opportunity_a_record, opportunity_b_record])
    db.commit()
    db.refresh(opportunity_a_record)
    db.refresh(opportunity_b_record)

    opportunity_a = multi_judge.run_judgments(
        db,
        question="Is the supplied proposition supported?",
        evidence_ids=[evidence.id],
        judges=[judge],
        opportunity_id=opportunity_a_record.id,
    )[0]
    opportunity_a_repeat = multi_judge.run_judgments(
        db,
        question="Is the supplied proposition supported?",
        evidence_ids=[evidence.id],
        judges=[judge],
        opportunity_id=opportunity_a_record.id,
    )[0]
    opportunity_b = multi_judge.run_judgments(
        db,
        question="Is the supplied proposition supported?",
        evidence_ids=[evidence.id],
        judges=[judge],
        opportunity_id=opportunity_b_record.id,
    )[0]

    assert opportunity_a.id == opportunity_a_repeat.id
    assert opportunity_a.id != opportunity_b.id
    assert opportunity_a.opportunity_id == opportunity_a_record.id
    assert opportunity_b.opportunity_id == opportunity_b_record.id



def test_unavailable_judgment_can_recover_for_same_evidence(db):
    evidence = evidence_fixture(db)
    availability = {"ready": False}
    judge = multi_judge.JudgeSpec(
        name="recovering-judge",
        provider="test-provider",
        model="recovering-judge-model",
        evaluate=positive_judge,
        available=lambda: availability["ready"],
    )

    failed = multi_judge.run_judgments(
        db,
        question="Does the same evidence support recurring scheduling pain?",
        evidence_ids=[evidence.id],
        judges=[judge],
    )[0]
    assert failed.status == "failed"
    assert (failed.error or "").startswith("judge unavailable:")

    availability["ready"] = True
    recovered = multi_judge.run_judgments(
        db,
        question="Does the same evidence support recurring scheduling pain?",
        evidence_ids=[evidence.id],
        judges=[judge],
    )[0]
    repeated = multi_judge.run_judgments(
        db,
        question="Does the same evidence support recurring scheduling pain?",
        evidence_ids=[evidence.id],
        judges=[judge],
    )[0]

    assert recovered.status == "completed"
    assert recovered.id != failed.id
    assert repeated.id == recovered.id
    assert db.query(models.Judgment).filter_by(judgment_key=recovered.judgment_key).count() == 2
    assert db.query(models.ResearchQuestion).count() == 0



def test_default_provider_judge_sees_only_explicitly_shareable_public_evidence(db, monkeypatch):
    from app.config import settings

    public = models.Evidence(
        source="public-test-source",
        title="Public report title",
        claim="Public report states a bounded factual claim.",
        content="PUBLIC_EXCERPT_VISIBLE_TO_PROVIDER",
        canonical_url="https://example.gov.np/report",
        source_kind="REAL",
        source_type="third_party",
        consent_status="not_required",
        collection_status="collected",
    )
    private = models.Evidence(
        source="private-inquiry",
        title="Private inquiry",
        claim="PRIVATE_CLAIM_MUST_NEVER_LEAK",
        content="PRIVATE_RAW_CONTENT_MUST_NEVER_LEAK",
        canonical_url="https://example.com/private",
        source_kind="REAL",
        source_type="firsthand",
        consent_status="granted",
        collection_status="collected",
    )
    pending = models.Evidence(
        source="pending-publication",
        title="Pending consent title",
        content="PENDING_CONSENT_CONTENT_MUST_NEVER_LEAK",
        canonical_url="https://example.com/pending",
        source_kind="REAL",
        source_type="third_party",
        consent_status="pending",
        collection_status="collected",
    )
    db.add_all([public, private, pending])
    db.commit()
    db.refresh(public)
    db.refresh(private)
    db.refresh(pending)
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "FORGEOS_OPENAI_JUDGE_ENABLED", False)
    monkeypatch.delenv("VERCEL", raising=False)

    sent_prompts = []

    class FakeTool:
        def is_available(self):
            return True

        def execute(self, prompt, **kwargs):
            sent_prompts.append(prompt)
            return {
                "label": "uncertain",
                "conclusion": "The permitted metadata does not establish the broader claim.",
                "reasoning": "Only bounded public source material was supplied.",
                "uncertainty": "Underlying corroboration and applicability remain unassessed.",
            }

    class FakeRegistry:
        def get(self, name):
            assert name == "local-qwen3-coder"
            return FakeTool()

    monkeypatch.setattr(multi_judge, "default_registry", lambda: FakeRegistry())
    specs = multi_judge._default_judges(evidence=[public, private, pending])

    assert len(specs) == 1
    assert specs[0].evidence_ids == (public.id,)
    result = specs[0].evaluate(
        "Does the evidence support the claim?",
        [public, private, pending],
    )
    assert result["label"] == "uncertain"
    prompt = sent_prompts[0]
    assert "PUBLIC_EXCERPT_VISIBLE_TO_PROVIDER" in prompt
    assert "PRIVATE_CLAIM_MUST_NEVER_LEAK" not in prompt
    assert "PRIVATE_RAW_CONTENT_MUST_NEVER_LEAK" not in prompt
    assert "PENDING_CONSENT_CONTENT_MUST_NEVER_LEAK" not in prompt


def test_default_judgment_records_only_the_evidence_the_provider_received(db, monkeypatch):
    from app.config import settings

    public = models.Evidence(
        source="public-test-source",
        title="Public report title",
        claim="Public report states a bounded factual claim.",
        content="Public factual excerpt.",
        canonical_url="https://example.gov.np/report",
        source_kind="REAL",
        source_type="third_party",
        consent_status="not_required",
        collection_status="collected",
    )
    private = models.Evidence(
        source="private-inquiry",
        title="Private inquiry",
        content="Do not share this.",
        canonical_url="https://example.com/private",
        source_kind="REAL",
        source_type="firsthand",
        consent_status="granted",
        collection_status="collected",
    )
    db.add_all([public, private])
    db.commit()
    db.refresh(public)
    db.refresh(private)
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "FORGEOS_OPENAI_JUDGE_ENABLED", False)
    monkeypatch.delenv("VERCEL", raising=False)

    class FakeTool:
        def is_available(self):
            return True

        def execute(self, prompt, **kwargs):
            assert "Public factual excerpt." in prompt
            assert "Do not share this." not in prompt
            return {
                "label": "uncertain",
                "conclusion": "The source is insufficient for a broader conclusion.",
                "reasoning": "Only one permitted source excerpt was evaluated.",
                "uncertainty": "Independent corroboration is not present.",
            }

    class FakeRegistry:
        def get(self, name):
            return FakeTool()

    monkeypatch.setattr(multi_judge, "default_registry", lambda: FakeRegistry())
    original_default_factory = multi_judge._default_judges
    monkeypatch.setattr(multi_judge, "_default_judges", lambda evidence=None: original_default_factory(evidence=evidence))

    judgment = multi_judge.run_judgments(
        db,
        question="Does the source establish this claim?",
        evidence_ids=[public.id, private.id],
    )[0]

    assert judgment.status == "completed"
    assert judgment.evidence_ids == str(public.id)
    assert db.query(models.EvidenceRelationship).filter_by(
        judgment_id=judgment.id,
        evidence_id=public.id,
    ).count() == 1
    assert db.query(models.EvidenceRelationship).filter_by(
        judgment_id=judgment.id,
        evidence_id=private.id,
    ).count() == 0

    comparison = multi_judge.compare_judgments(
        db,
        question="Does the source establish this claim?",
        judgment_ids=[judgment.id],
        evidence_ids=[public.id, private.id],
    )
    assert comparison.outcome == "insufficient_judges"
    assert comparison.evidence_ids == str(public.id)


def test_default_judge_has_no_available_provider_context_on_vercel(monkeypatch):
    from app.config import settings
    from app.services.tool_registry import default_registry

    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    monkeypatch.setenv("VERCEL", "1")
    tool = default_registry().get("local-qwen3-coder")
    assert tool.is_available() is False
