from app import models
from app.services import collector_runner, multi_judge, research_planner, research_task_engine
from app.services import evidence_graph
from app.services.observer_engine import ObserverEngine


class SourceCollectorFixture:
    source_name = "fixture-source"
    source_type = "test"
    fail = False
    items = []

    def collect(self, query=None):
        if self.fail:
            raise RuntimeError("fixture source failed")
        return list(self.items)

    def normalize(self, raw_item):
        return {
            "source": self.source_name,
            "content": raw_item["content"],
            "title": raw_item.get("title"),
            "canonical_url": raw_item.get("url"),
            "external_id": raw_item.get("external_id"),
            "metadata": raw_item.get("metadata", {}),
        }


def make_claim_task(db, suffix=""):
    claim, _ = evidence_graph.create_or_get_claim(
        db,
        f"Businesses pay for repair scheduling services{suffix}.",
        epistemic_state="observed",
    )
    question = models.ResearchQuestion(
        question=f"Verify whether businesses pay for repair scheduling services{suffix}.",
        source_claim_id=claim.id,
        priority_score=90,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        claim_id=claim.id,
        source="fixture-source",
        query=question.question,
        objective=question.question,
    )
    return claim, task


def judge_specs():
    return [
        multi_judge.JudgeSpec(
            name="judge-support",
            provider="fixture-provider",
            model="fixture-support-v1",
            evaluate=lambda question, evidence: {
                "label": "positive",
                "conclusion": "Independent evidence supports the claim.",
                "reasoning": "A source describes active paid use.",
            },
        ),
        multi_judge.JudgeSpec(
            name="judge-cautious",
            provider="fixture-provider",
            model="fixture-cautious-v1",
            evaluate=lambda question, evidence: {
                "label": "uncertain",
                "conclusion": "Evidence is insufficient to verify payment.",
                "reasoning": "No transaction record is present.",
                "uncertainty": "pricing remains unresolved",
            },
        ),
    ]


def test_media_claim_creates_multiple_source_tasks_without_duplication(db):
    claim, _ = make_claim_task(db)
    question = db.query(models.ResearchQuestion).filter_by(source_claim_id=claim.id).one()

    tasks = research_planner.plan_tasks_for_question(db, question)
    again = research_planner.plan_tasks_for_question(db, question)

    assert len(tasks) >= 2
    assert len(again) == 0
    assert {task.source for task in tasks}.issuperset({"reddit", "github"})
    assert all(task.claim_id == claim.id for task in tasks)


def test_successful_collection_persists_evidence_and_triggers_p3(db, monkeypatch):
    claim, task = make_claim_task(db)
    SourceCollectorFixture.items = [
        {
            "content": "A contractor pays monthly for repair scheduling software.",
            "title": "Pricing page",
            "url": "https://example.test/pricing",
            "external_id": "pricing-1",
            "metadata": {"claim_relation": "supports", "publisher": "Example"},
        }
    ]
    SourceCollectorFixture.fail = False
    monkeypatch.setitem(collector_runner.COLLECTORS, "fixture-source", SourceCollectorFixture)
    monkeypatch.setattr(multi_judge, "_default_judges", judge_specs)

    result = collector_runner.execute_task(db, task)

    assert result["status"] == "completed"
    assert result["evidence_found"] == 1
    evidence = db.query(models.Evidence).one()
    edge = db.query(models.EvidenceRelationship).filter_by(claim_id=claim.id, evidence_id=evidence.id).one()
    assert edge.relation_type == "supports"
    assert db.query(models.Judgment).count() == 2
    comparison = db.query(models.JudgmentComparison).one()
    assert comparison.outcome == "partial_agreement"
    assert comparison.follow_up_question_id is not None
    assert db.get(models.ResearchTask, task.id).results["comparison_id"] == comparison.id


def test_unavailable_and_failed_sources_are_recorded_without_fabrication(db, monkeypatch):
    claim, task = make_claim_task(db)
    task.source = "missing-source"
    db.commit()
    result = collector_runner.execute_task(db, task)
    assert result["status"] == "failed"
    assert "No collector registered" in result["reason"]
    assert db.get(models.ResearchTask, task.id).errors

    failing = SourceCollectorFixture
    failing.fail = True
    monkeypatch.setitem(collector_runner.COLLECTORS, "fixture-source", failing)
    _, failed_task = make_claim_task(db, suffix=" after source failure")
    failed = collector_runner.execute_task(db, failed_task)
    assert failed["status"] == "failed"
    assert "fixture source failed" in failed["reason"]
    assert db.query(models.Evidence).count() == 0
    assert db.query(models.Judgment).count() == 0


def test_duplicate_research_reuses_evidence_and_new_source_rejudges(db, monkeypatch):
    claim, first_task = make_claim_task(db)
    SourceCollectorFixture.fail = False
    SourceCollectorFixture.items = [{
        "content": "Businesses pay monthly for repair scheduling software.",
        "url": "https://example.test/one",
        "external_id": "one",
        "metadata": {"claim_relation": "supports"},
    }]
    monkeypatch.setitem(collector_runner.COLLECTORS, "fixture-source", SourceCollectorFixture)
    monkeypatch.setattr(multi_judge, "_default_judges", lambda: judge_specs()[:1])

    first = collector_runner.execute_task(db, first_task)
    repeated = collector_runner.execute_task(db, db.get(models.ResearchTask, first_task.id))
    assert first["status"] == "completed"
    assert repeated["reused"] is True
    assert db.query(models.Evidence).count() == 1
    assert db.query(models.Judgment).count() == 1

    second_task = research_task_engine.create_task(
        db,
        question_id=first_task.question_id,
        claim_id=claim.id,
        source="fixture-source",
        query="independent pricing evidence",
        objective="Verify whether businesses pay for repair scheduling services.",
    )
    SourceCollectorFixture.items = [{
        "content": "A different company lists a paid repair scheduling plan.",
        "url": "https://example.test/two",
        "external_id": "two",
        "metadata": {"claim_relation": "supports"},
    }]
    second = collector_runner.execute_task(db, second_task)
    assert second["evidence_found"] == 1
    assert db.query(models.Evidence).count() == 2
    assert db.query(models.Judgment).count() == 2
    assert len(db.get(models.ResearchTask, second_task.id).results["judgment_ids"]) == 1


def test_contradictory_evidence_preserves_contested_claim_and_no_revenue(db, monkeypatch):
    claim, task = make_claim_task(db)
    SourceCollectorFixture.items = [{
        "content": "Customers explicitly do not pay for repair scheduling services.",
        "url": "https://example.test/contradiction",
        "external_id": "contradiction",
        "metadata": {"claim_relation": "contradicts"},
    }]
    monkeypatch.setitem(collector_runner.COLLECTORS, "fixture-source", SourceCollectorFixture)
    monkeypatch.setattr(multi_judge, "_default_judges", judge_specs)

    collector_runner.execute_task(db, task)

    assert db.get(models.Claim, claim.id).epistemic_state == "contested"
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Experiment).count() == 0
    assert db.query(models.Outcome).count() == 0


def test_default_collection_does_not_fetch_uncleared_feeds(monkeypatch):
    def explode(self, query=None):
        raise AssertionError("uncleared collector was called")

    for name in ("reddit", "github", "rss", "arxiv"):
        monkeypatch.setattr(collector_runner.COLLECTORS[name], "collect", explode)

    results = collector_runner.run_default_collection(db=None)
    assert [row["status"] for row in results] == ["skipped", "skipped", "skipped", "skipped"]
    assert all(row["signals_created"] == 0 for row in results)


def test_uncleared_task_source_fails_without_collection(db, monkeypatch):
    _, task = make_claim_task(db)
    task.source = "reddit"
    db.commit()

    def explode(self, query=None):
        raise AssertionError("reddit collector was called")

    monkeypatch.setattr(collector_runner.RedditCollector, "collect", explode)
    result = collector_runner.execute_task(db, task)
    assert result["status"] == "failed"
    assert "not cleared" in result["reason"]
    assert db.query(models.Signal).count() == 0
