from datetime import datetime, timedelta, timezone

from app import models
from app.services import collector_runner, tool_usefulness, research_task_engine
from app.services.tool_registry import ToolCapability, ToolRegistry


class FakeTool:
    def __init__(self, name):
        self.capability = ToolCapability(
            name=name,
            category="collection",
            capabilities=("collect",),
            reliability=0.5,
        )

    def is_available(self):
        return True

    def execute(self, payload, **kwargs):
        return payload


class UsefulCollector:
    source_name = "useful-source"
    source_type = "discussion"

    def collect(self, query=None):
        return [{
            "content": "Customers pay monthly for this repair workflow.",
            "metadata": {
                "url": "https://example.test/useful",
                "external_id": "useful-1",
                "claim_relation": "supports",
            },
        }]

    def normalize(self, raw):
        return {
            "source": self.source_name,
            "content": raw["content"],
            "canonical_url": raw["metadata"]["url"],
            "external_id": raw["metadata"]["external_id"],
            "metadata": raw["metadata"],
        }


def _create_test_task(db, name, *, claim_id=None):
    question = models.ResearchQuestion(question=f"TEST research task for {name}")
    db.add(question)
    db.flush()
    task = models.ResearchTask(
        question_id=question.id,
        claim_id=claim_id,
        source="test",
        query=name,
    )
    db.add(task)
    db.flush()
    return task


def test_successful_useful_source_usage_is_persisted(db, monkeypatch):
    question = models.ResearchQuestion(question="Does the repair workflow have paying customers?")
    claim = models.Claim(statement="Businesses pay for the repair workflow.", normalized_statement="businesses pay for the repair workflow")
    db.add_all([question, claim])
    db.commit()
    db.refresh(question)
    db.refresh(claim)
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        claim_id=claim.id,
        source="useful-source",
        query=question.question,
        objective=question.question,
    )
    monkeypatch.setitem(collector_runner.COLLECTORS, "useful-source", UsefulCollector)

    result = collector_runner.execute_task(db, task)

    assert result["status"] == "completed"
    tool = db.query(models.ToolUsageEvent).filter_by(tool_name="collector:useful-source").one()
    source = db.query(models.SourceUsageEvent).filter_by(source="useful-source").one()
    assert tool.success is True
    assert tool.result_count == 1
    assert tool.useful_result_count == 1
    assert tool.novel_result_count == 1
    assert source.useful_evidence_count == 1
    assert source.contradicted_claim_count == 0
    assert tool.cost is None


def test_failed_tool_usage_records_failure_without_fabricated_results(db):
    task = _create_test_task(db, "blocked collector timeout")
    event = tool_usefulness.record_usage(
        db,
        tool_name="collector:blocked",
        source="blocked",
        source_type="web",
        query="pricing",
        research_task_id=task.id,
        claim_id=None,
        result_count=None,
        useful_result_count=None,
        novel_result_count=None,
        verified_result_count=None,
        duplicate_result_count=None,
        corroborated_evidence_count=None,
        contradicted_claim_count=None,
        freshness=None,
        latency_ms=12.0,
        success=False,
        failure_kind="timeout",
    )
    assert event[0].success is False
    assert event[0].result_count is None
    assert tool_usefulness.tool_summary(db, "collector:blocked")["failures"] == 1


def test_duplicate_performance_event_is_ignored(db):
    task = _create_test_task(db, "repeat collector")
    kwargs = dict(
        tool_name="collector:repeat", source="repeat", source_type="code", query="x",
        research_task_id=task.id, claim_id=None, result_count=2, useful_result_count=1,
        novel_result_count=1, verified_result_count=0, duplicate_result_count=1,
        corroborated_evidence_count=0, contradicted_claim_count=0, freshness=90,
        latency_ms=4, success=True, result_ids=[10, 11],
    )
    assert tool_usefulness.record_usage(db, **kwargs) is not None
    assert tool_usefulness.record_usage(db, **kwargs) is None
    assert db.query(models.ToolUsageEvent).count() == 1
    assert db.query(models.SourceUsageEvent).count() == 1


def test_recent_performance_and_task_specific_source_history(db):
    old = models.ToolUsageEvent(
        tool_name="tool-a", result_count=10, useful_result_count=1,
        success=True, event_key="old", created_at=datetime.now(timezone.utc) - timedelta(days=90),
    )
    recent = models.ToolUsageEvent(
        tool_name="tool-a", result_count=2, useful_result_count=2,
        success=True, event_key="recent", created_at=datetime.now(timezone.utc),
    )
    db.add_all([old, recent])
    db.commit()
    summary = tool_usefulness.tool_summary(db, "tool-a")
    assert summary["useful_rate"] == 0.25
    assert summary["recent_useful_rate"] == 1.0
    assert tool_usefulness.learned_score(summary) > summary["useful_rate"]

    claims = [
        models.Claim(
            statement=f"TEST claim {index}",
            normalized_statement=f"test claim {index}",
        )
        for index in (1, 2)
    ]
    db.add_all(claims)
    db.flush()
    reddit_task = _create_test_task(db, "reddit pain research", claim_id=claims[0].id)
    github_task = _create_test_task(db, "github adoption research", claim_id=claims[1].id)
    tool_usefulness.record_usage(
        db, tool_name="tool-a", source="reddit", source_type="discussion", query="pain",
        research_task_id=reddit_task.id, claim_id=claims[0].id, result_count=2, useful_result_count=2,
        novel_result_count=2, verified_result_count=1, duplicate_result_count=0,
        corroborated_evidence_count=1, contradicted_claim_count=0, freshness=100,
        latency_ms=2, success=True, result_ids=[20, 21],
    )
    tool_usefulness.record_usage(
        db, tool_name="tool-a", source="github", source_type="code", query="adoption",
        research_task_id=github_task.id, claim_id=claims[1].id, result_count=2, useful_result_count=0,
        novel_result_count=0, verified_result_count=0, duplicate_result_count=2,
        corroborated_evidence_count=0, contradicted_claim_count=0, freshness=40,
        latency_ms=2, success=True, result_ids=[30, 31],
    )
    assert tool_usefulness.source_summary(db, "reddit")["useful_rate"] == 1.0
    assert tool_usefulness.source_summary(db, "github")["duplicate_count"] == 2


def test_registry_uses_learned_performance_and_deterministic_exploration(db):
    registry = ToolRegistry([FakeTool("alpha"), FakeTool("beta")])
    alpha_task = _create_test_task(db, "alpha performance")
    beta_task = _create_test_task(db, "beta performance")
    tool_usefulness.record_usage(
        db, tool_name="alpha", source="alpha", source_type="test", query="q",
        research_task_id=alpha_task.id, claim_id=None, result_count=10, useful_result_count=1,
        novel_result_count=1, verified_result_count=0, duplicate_result_count=0,
        corroborated_evidence_count=0, contradicted_claim_count=0, freshness=80,
        latency_ms=1, success=True, result_ids=[1],
    )
    tool_usefulness.record_usage(
        db, tool_name="beta", source="beta", source_type="test", query="q",
        research_task_id=beta_task.id, claim_id=None, result_count=2, useful_result_count=2,
        novel_result_count=2, verified_result_count=1, duplicate_result_count=0,
        corroborated_evidence_count=1, contradicted_claim_count=0, freshness=100,
        latency_ms=1, success=True, result_ids=[2, 3],
    )
    selected = registry.select(category="collection", capability="collect", db=db, explore=False)
    assert selected.tool.capability.name == "beta"

    key = next(str(i) for i in range(1000) if int(__import__("hashlib").sha256(str(i).encode()).hexdigest()[:8], 16) % 5 == 0)
    explored = registry.select(category="collection", capability="collect", db=db, explore=True, exploration_key=key)
    assert explored.tool.capability.name in {"alpha", "beta"}
