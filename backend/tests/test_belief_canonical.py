from app import models
from app.services.belief_engine import BeliefEngine
from app.services.pattern_engine import run_pattern_detection
from app.services.belief_engine import repair_historical_beliefs


def _signal(content: str, url: str | None = None):
    return models.Signal(source="rss", source_type="external", content=content, canonical_url=url)


def test_keyword_permutations_become_one_hypothesis(db):
    texts = [
        "small business customer support data workflow is slow",
        "customer support for a small business needs better data",
        "data and customer support burden small business teams",
    ]
    for text in texts:
        db.add(_signal(text, url="https://example.com/same-note"))
        db.add(_signal(text, url="https://example.com/same-note"))
    db.commit()
    first = run_pattern_detection(db)
    second = run_pattern_detection(db)
    engine = BeliefEngine(db)
    for pattern in first:
        ids = [int(item) for item in pattern.origin_signal_ids.split(",") if item]
        engine.form_belief_from_pattern(pattern, ids)
    for pattern in second:
        ids = [int(item) for item in pattern.origin_signal_ids.split(",") if item]
        engine.form_belief_from_pattern(pattern, ids)
    beliefs = db.query(models.Belief).all()
    assert len(beliefs) == 1
    assert "real, addressable business problem" not in beliefs[0].statement
    assert "Uncorroborated keyword hypothesis" in beliefs[0].statement
    assert beliefs[0].confidence_score < 95


def test_repeated_copies_of_one_source_do_not_count_as_independent_confirmation(db):
    for index in range(20):
        db.add(_signal(
            "small business customer support data workflow is slow",
            url="https://example.com/one-source",
        ))
    db.add(_signal(
        "small business customer support data workflow is slow",
        url="https://example.com/independent-source",
    ))
    db.commit()

    patterns = run_pattern_detection(db)

    assert len(patterns) == 1
    assert patterns[0].frequency == 21
    assert patterns[0].confidence_score < 20


def test_historical_beliefs_merge_without_losing_provenance(db):
    first_signal = _signal("customer support data workflow")
    second_signal = _signal("data workflow customer support")
    db.add_all([first_signal, second_signal])
    db.commit()
    pattern_a = models.Pattern(
        title="Recurring theme: support, customer, data, workflow",
        description="legacy",
        origin_signal_ids=f"{first_signal.id}",
    )
    pattern_b = models.Pattern(
        title="Recurring theme: workflow, data, customer, support",
        description="legacy",
        origin_signal_ids=f"{second_signal.id}",
    )
    db.add_all([pattern_a, pattern_b])
    db.commit()
    duplicate = models.Belief(
        statement='Recurring signals about "support, customer, data, workflow" indicate a real, addressable business problem.',
        pattern_id=pattern_a.id,
        supporting_signal_ids=str(first_signal.id),
        confidence_score=80,
    )
    canonical = models.Belief(
        statement='Uncorroborated keyword hypothesis: "customer, data, support, workflow". This is not a verified business problem, demand claim, or price.',
        pattern_id=pattern_b.id,
        supporting_signal_ids=str(second_signal.id),
        confidence_score=60,
    )
    db.add_all([duplicate, canonical])
    db.commit()
    db.add(models.Evidence(belief_id=duplicate.id, signal_id=first_signal.id, content=first_signal.content))
    db.commit()

    assert repair_historical_beliefs(db) == 1
    db.refresh(duplicate)
    db.refresh(canonical)
    assert db.query(models.Belief).count() == 2
    assert duplicate.merged_into_id == canonical.id
    assert canonical.supporting_signal_ids == f"{first_signal.id},{second_signal.id}"
    assert canonical.confidence_score == 60
    assert db.query(models.Evidence).filter_by(belief_id=canonical.id).count() == 1
    assert "real, addressable business problem" not in canonical.statement
    assert repair_historical_beliefs(db) == 0


def test_oversized_keyword_hypothesis_stays_stored_but_is_not_listed(db):
    from app.services.belief_engine import BeliefEngine
    words = ", ".join(f"word{i}" for i in range(20))
    row = models.Belief(
        statement=f'Uncorroborated keyword hypothesis: "{words}". This is not a verified business problem, demand claim, or price.',
        confidence_score=10,
    )
    db.add(row)
    db.commit()
    listed = BeliefEngine(db).list_beliefs()
    assert row.id not in {item.id for item in listed}
    assert db.get(models.Belief, row.id) is not None


def test_oversized_hypothesis_does_not_open_a_research_question(db):
    from app.services.curiosity_engine import CuriosityEngine
    words = ", ".join(f"word{i}" for i in range(20))
    db.add(models.Belief(
        statement=f'Uncorroborated keyword hypothesis: "{words}". This is not a verified business problem, demand claim, or price.',
        confidence_score=10,
    ))
    db.commit()
    assert CuriosityEngine(db).find_low_confidence_beliefs() == []


def test_near_duplicate_historical_beliefs_collapse_to_one(db):
    shared = models.Signal(source="rss", source_type="external", content="customer support software")
    db.add(shared)
    db.commit()
    rows = []
    for words in (
        "business, customer support, small, software",
        "customer support, data, small, software",
        "customer, customer support, small, software",
    ):
        rows.append(models.Belief(
            statement=f'Recurring signals about "{words}" indicate a real, addressable business problem.',
            supporting_signal_ids=str(shared.id),
            confidence_score=40,
        ))
    db.add_all(rows)
    db.commit()
    assert repair_historical_beliefs(db) == 2
    active = db.query(models.Belief).filter(models.Belief.merged_into_id.is_(None)).all()
    assert len(active) == 1
    assert "real, addressable business problem" not in active[0].statement
    assert db.query(models.Signal).count() == 1
