"""Operating Model v4: substrate bets, provenance, dormancy, verifier, frontier."""

import pytest

from app import models
from app.services import operating_v4


def _evidence(db, source_type="firsthand"):
    ev = models.Evidence(
        claim="test", content="test", source="test", source_type=source_type
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def test_bet_is_substrate_projection(db):
    b = operating_v4.create_bet(
        db,
        claim="Fast replies recover sales",
        constraint="Response presence, not demand",
        test="One seller, one week",
        kill_criterion="No recovery",
        decision_rule="Recover >= 1 sale",
        skeptic_case="Sellers don't care about speed",
        money_at_risk="Rs 0",
    )
    assert b.entity_type == "bet"
    assert isinstance(b, models.SubstrateEntity)
    # No separate bets table.
    assert not hasattr(models, "Bet")
    live = operating_v4.live_bets(db)
    assert len(live) == 1


def test_bet_wip_limit(db):
    for i in range(3):
        operating_v4.create_bet(
            db, claim=f"c{i}", constraint="x", test="t",
            kill_criterion="k", decision_rule="r", skeptic_case="s",
        )
    with pytest.raises(ValueError, match="WIP limit"):
        operating_v4.create_bet(
            db, claim="c3", constraint="x", test="t",
            kill_criterion="k", decision_rule="r", skeptic_case="s",
        )


def test_agent_written_capped_l0(db):
    ev = _evidence(db, "agent_written")
    operating_v4.set_proof_level(db, ev.id, 4, source_type="agent_written")
    assert db.get(models.Evidence, ev.id).proof_level == 0


def test_secondhand_capped_l1(db):
    ev = _evidence(db, "secondhand")
    operating_v4.set_proof_level(db, ev.id, 5, source_type="secondhand")
    assert db.get(models.Evidence, ev.id).proof_level == 1


def test_l5_requires_verifier(db):
    ev = _evidence(db, "firsthand")
    with pytest.raises(ValueError, match="counterparty confirmation"):
        operating_v4.set_proof_level(db, ev.id, 5)
    operating_v4.set_proof_level(db, ev.id, 5, verifier="counterparty: seller confirmed")
    assert db.get(models.Evidence, ev.id).proof_level == 5


def test_starved_blocks_builds_except_obligations(db):
    assert operating_v4.is_starved(db) is True
    with pytest.raises(ValueError, match="STARVED"):
        operating_v4.check_build_allowed(db)
    # System Obligations exempt.
    operating_v4.check_build_allowed(db, is_system_obligation=True)


def test_verification_rejects_incomplete(db):
    with pytest.raises(ValueError, match="rejected"):
        operating_v4.record_verification(db, "", "content", "1/1", True)
    rec = operating_v4.record_verification(db, "abc123", "fetched", "198/198", True)
    assert rec.passed is True


def test_dormancy_freeze_and_resume(tmp_path, db, monkeypatch):
    assert operating_v4.is_dormant(db) is False
    operating_v4.enter_dormancy(db)
    assert operating_v4.is_dormant(db) is True
    with pytest.raises(ValueError, match="Dormant"):
        operating_v4.check_agent_run_allowed(db)
    # Resume requires docs/RUN_STATE.md.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="RUN_STATE.md"):
        operating_v4.exit_dormancy(db)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "RUN_STATE.md").write_text("# run state")
    operating_v4.exit_dormancy(db, run_state_path="docs/RUN_STATE.md")
    assert operating_v4.is_dormant(db) is False


def test_frontier_challenge_monthly(db):
    fc = operating_v4.record_frontier_challenge(
        db, "2026-10", "Lead-gen SaaS", "SaaS charges before value; we charge after."
    )
    assert fc.month == "2026-10"
    with pytest.raises(ValueError, match="already recorded"):
        operating_v4.record_frontier_challenge(db, "2026-10", "x", "y")


def test_scoreboard_readonly_shape(db):
    board = operating_v4.scoreboard(db)
    for field in (
        "days_since_last_contact",
        "observations",
        "conversations",
        "live_bets",
        "bets_killed",
        "bets_amplified",
        "highest_proof_level",
        "verified_rupees",
        "sampling_gaps",
        "who_not_heard_from",
        "owner_time_used",
        "owner_budget_remaining",
        "starved",
    ):
        assert field in board, f"scoreboard missing {field}"
    assert board["starved"] is True
    assert board["verified_rupees"] == 0.0
