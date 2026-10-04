from app import models
from app.services.belief_engine import (
    BeliefEngine,
    is_presentable_belief,
    qualifies_as_hypothesis,
    relabel_keyword_bags_as_observations,
)
from app.services.belief_engine import repair_historical_beliefs
from app.services.pattern_engine import run_pattern_detection


OBS_SUFFIX = "An observation, not a hypothesis"


def _signal(content: str, url: str | None = None):
    return models.Signal(source="rss", source_type="external", content=content, canonical_url=url)


def _qualified_belief(signal_id: int, **overrides):
    fields = dict(
        statement="Kathmandu retailers lose weekend sales to slow inquiry replies.",
        actor_segment="Kathmandu retail shops taking inquiries on social apps",
        need_pain="Missed sales from slow replies on weekends",
        give_up="A share of each recovered sale",
        supporting_signal_ids=str(signal_id),
        confidence_score=60,
        label="hypothesis",
    )
    fields.update(overrides)
    return models.Belief(**fields)


def test_keyword_permutations_become_one_observation(db):
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
    row = beliefs[0]
    # The generator must never call a keyword bag a hypothesis.
    assert "hypothesis" not in row.statement.lower().replace("not a hypothesis", "")
    assert "Observed keyword cluster" in row.statement
    assert row.label == "observation"
    assert not qualifies_as_hypothesis(row)
    assert not is_presentable_belief(row)
    assert row.confidence_score < 95


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
        label="observation",
    )
    canonical = models.Belief(
        statement='Observed keyword cluster: "customer, data, support, workflow". An observation, not a hypothesis — no actor, need, give-up, or evidence attached.',
        pattern_id=pattern_b.id,
        supporting_signal_ids=str(second_signal.id),
        confidence_score=60,
        label="observation",
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
    assert "Observed keyword cluster" in canonical.statement
    assert repair_historical_beliefs(db) == 0


def test_oversized_keyword_observation_stays_stored_but_is_not_listed(db):
    words = ", ".join(f"word{i}" for i in range(20))
    row = models.Belief(
        statement=f'Observed keyword cluster: "{words}". {OBS_SUFFIX} — no actor, need, give-up, or evidence attached.',
        confidence_score=10,
        label="observation",
    )
    db.add(row)
    db.commit()
    listed = BeliefEngine(db).list_beliefs()
    assert row.id not in {item.id for item in listed}
    assert db.get(models.Belief, row.id) is not None


def test_oversized_observation_does_not_open_a_research_question(db):
    from app.services.curiosity_engine import CuriosityEngine
    words = ", ".join(f"word{i}" for i in range(20))
    db.add(models.Belief(
        statement=f'Observed keyword cluster: "{words}". {OBS_SUFFIX} — no actor, need, give-up, or evidence attached.',
        confidence_score=10,
        label="observation",
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
            label="observation",
        ))
    db.add_all(rows)
    db.commit()
    assert repair_historical_beliefs(db) == 2
    active = db.query(models.Belief).filter(models.Belief.merged_into_id.is_(None)).all()
    assert len(active) == 1
    assert "real, addressable business problem" not in active[0].statement
    assert db.query(models.Signal).count() == 1


# --- The hypothesis gate: actor + need + give-up + evidence, or it is an observation. ---


def test_qualified_hypothesis_is_presentable(db):
    sig = _signal("retailer missed weekend sale")
    db.add(sig)
    db.commit()
    row = _qualified_belief(sig.id)
    db.add(row)
    db.commit()
    assert qualifies_as_hypothesis(row)
    assert is_presentable_belief(row)
    assert row.id in {b.id for b in BeliefEngine(db).list_beliefs()}


def test_missing_any_field_means_observation_not_presentable(db):
    sig = _signal("retailer missed weekend sale")
    db.add(sig)
    db.commit()
    cases = [
        dict(actor_segment=""),
        dict(actor_segment=None),
        dict(need_pain="  "),
        dict(give_up=None),
        dict(supporting_signal_ids=""),
        dict(supporting_signal_ids=None),
    ]
    for i, overrides in enumerate(cases):
        row = _qualified_belief(sig.id, statement=f"case {i}", **overrides)
        db.add(row)
    db.commit()
    for row in db.query(models.Belief).all():
        assert not qualifies_as_hypothesis(row), row.statement
        assert not is_presentable_belief(row), row.statement
    assert BeliefEngine(db).list_beliefs() == []


def test_relabel_archives_keyword_bags_with_reason_and_deletes_nothing(db):
    sig = _signal("legacy signal")
    db.add(sig)
    db.commit()
    old_statement = (
        'Uncorroborated keyword hypothesis: "data, support". '
        "This is not a verified business problem, demand claim, or price."
    )
    row = models.Belief(
        statement=old_statement,
        supporting_signal_ids=str(sig.id),
        confidence_score=40,
        label="hypothesis",
    )
    db.add(row)
    db.commit()
    row_id = row.id

    assert relabel_keyword_bags_as_observations(db) == 1

    db.refresh(row)
    assert db.get(models.Belief, row_id) is not None  # nothing deleted
    assert row.label == "observation"
    assert row.relabel_reason is not None and "keyword-bag" in row.relabel_reason
    assert "Uncorroborated keyword hypothesis" not in row.statement
    assert "Observed keyword cluster" in row.statement
    assert not qualifies_as_hypothesis(row)

    # Second run is a no-op.
    assert relabel_keyword_bags_as_observations(db) == 0
