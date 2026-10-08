"""Unknown-unknown discovery loop: two selection lanes on the existing Bet projection.

Discovery is a *lane* on the existing candidate/Bet mechanism (Selection v0),
not a new table, primitive, or queue. These tests pin the contract:

* known-unknown candidates keep working exactly as before;
* discovery candidates enter the SAME pool through the SAME admission gates;
* a discovery finding becomes a known unknown only with valid provenance;
* nothing is fabricated when source evidence is absent;
* authorization and execution boundaries stay intact.
"""

import pytest

from fastapi import HTTPException

from app import models
from app.services import operating_v4
from app.services import discovery_selection


def _assessments(**overrides):
    base = {
        dimension: {"level": "unassessed", "provenance": "unassessed"}
        for dimension in operating_v4.SELECTION_DIMENSIONS
    }
    base.update(overrides)
    return base


def _confirmed(level):
    return {"level": level, "provenance": "observed"}


def _known_candidate(db, **kw):
    args = dict(
        source_unknown_id="D2",
        claim="Do owners want to be found?",
        why_it_matters="Sizes the wedge",
        disconfirming_test="Ask five owners",
        kill_rule="No owner names presence as the constraint",
        consent_requirement="owner consent; no contact by Hami",
        bounded_cost="5 owner hours",
        bounded_harm="none",
        time_to_first_evidence_days=7,
        horizon_relation="inside",
        assessments=_assessments(),
    )
    args.update(kw)
    return operating_v4.create_candidate(db, **args)


def _discovery_candidate(db, **kw):
    args = dict(
        candidate_lane="unknown_unknown_discovery",
        source_unknown_id=None,
        claim="Probe parked domain for unrecognized unknowns",
        why_it_matters="High-stakes territory with no coverage",
        disconfirming_test="Bounded 2-hour review of domain signals",
        kill_rule="No anomaly found within 2 hours",
        consent_requirement="owner consent; no contact by Hami",
        bounded_cost="2 owner hours",
        bounded_harm="none",
        time_to_first_evidence_days=7,
        horizon_relation="outside",
        discovery_source="horizon_escape",
        discovery_basis="Domain is parked (outside watch horizon) with zero candidate coverage.",
        assessments=_assessments(),
    )
    args.update(kw)
    return operating_v4.create_candidate(db, **args)


def _ranked(db):
    return {
        item["candidate_id"]: item
        for item in operating_v4.select_next_candidates(db)["ranked_candidates"]
    }


# 1. known-unknown candidate still works; lane defaults to known_unknown.
def test_known_unknown_candidate_defaults_to_known_lane(db):
    bet = _known_candidate(db)
    ranked = _ranked(db)
    item = ranked[f"bet:{bet.id}"]
    assert item["candidate_lane"] == "known_unknown"
    assert item["discovery_source"] is None


# 2. discovery candidate can enter the same candidate pool.
def test_discovery_candidate_enters_same_pool(db):
    bet = _discovery_candidate(db)
    ranked = _ranked(db)
    item = ranked[f"bet:{bet.id}"]
    assert item["candidate_lane"] == "unknown_unknown_discovery"
    assert item["discovery_source"] == "horizon_escape"
    assert item["discovery_basis"].startswith("Domain is parked")


# 3. discovery candidate passes through existing admission gates.
def test_discovery_candidate_passes_admission_gates(db):
    bet = _discovery_candidate(
        db,
        assessments=_assessments(
            cost=_confirmed("low"),
            harm=_confirmed("low"),
        ),
    )
    item = _ranked(db)[f"bet:{bet.id}"]
    assert item["gate_blockers"] == []


# 4. failed discovery gate blocks candidate (BLOCKED, not low score).
def test_failed_discovery_gate_blocks_candidate(db):
    bet = _discovery_candidate(db, kill_rule="  ")
    item = _ranked(db)[f"bet:{bet.id}"]
    assert any("kill rule" in blocker for blocker in item["gate_blockers"])
    eligible = [
        item
        for item in operating_v4.select_next_candidates(db)["ranked_candidates"]
        if not item["gate_blockers"]
    ]
    assert f"bet:{bet.id}" not in {item["candidate_id"] for item in eligible}


# 5. model-proposed discovery is marked unconfirmed, never silently trusted.
def test_model_proposed_discovery_marked_unconfirmed(db):
    bet = _discovery_candidate(
        db,
        assessments=_assessments(
            stake={"level": "high", "provenance": "model-proposed"},
            cost=_confirmed("low"),
            harm=_confirmed("low"),
        ),
    )
    item = _ranked(db)[f"bet:{bet.id}"]
    assert item["assessments"]["stake"]["confirmed"] is False
    assert any("needs confirmation" in note for note in item["missing_information"])


# 6. discovery does not require a pre-existing named unknown;
#    the known lane still does.
def test_discovery_requires_no_preexisting_unknown(db):
    bet = _discovery_candidate(db, source_unknown_id=None)
    assert bet is not None
    with pytest.raises(ValueError, match="not in UNKNOWN_MAP"):
        _known_candidate(db, source_unknown_id="NOPE-NOT-REAL")


# 7. discovery may operate outside the current Horizon.
def test_discovery_may_operate_outside_horizon(db):
    bet = _discovery_candidate(db, horizon_relation="outside")
    item = _ranked(db)[f"bet:{bet.id}"]
    assert item["horizon_relation"] == "outside"


# 8. the current Horizon is not a hard universe boundary.
def test_horizon_is_not_universe_boundary(db):
    bet = _discovery_candidate(
        db,
        horizon_relation="outside",
        assessments=_assessments(cost=_confirmed("low"), harm=_confirmed("low")),
    )
    item = _ranked(db)[f"bet:{bet.id}"]
    assert item["gate_blockers"] == []
    assert not any("horizon" in blocker.lower() for blocker in item["gate_blockers"])


# 9. discovery does not automatically outrank known unknowns.
def test_discovery_does_not_auto_outrank(db):
    known = _known_candidate(
        db,
        assessments=_assessments(
            stake=_confirmed("high"),
            uncertainty=_confirmed("high"),
            cost=_confirmed("low"),
            harm=_confirmed("low"),
        ),
    )
    discovery = _discovery_candidate(
        db,
        assessments=_assessments(
            stake=_confirmed("low"),
            cost=_confirmed("low"),
            harm=_confirmed("low"),
        ),
    )
    ranked = operating_v4.select_next_candidates(db)["ranked_candidates"]
    positions = {item["candidate_id"]: item["rank"] for item in ranked}
    assert positions[f"bet:{known.id}"] < positions[f"bet:{discovery.id}"]


# 10. high-stake cheap known-unknown test outranks trivial discovery.
def test_high_stake_cheap_known_outranks_trivial_discovery(db):
    known = _known_candidate(
        db,
        assessments=_assessments(
            stake=_confirmed("high"),
            evidence_potential=_confirmed("high"),
            cost=_confirmed("low"),
            harm=_confirmed("low"),
        ),
    )
    discovery = _discovery_candidate(
        db,
        assessments=_assessments(
            stake=_confirmed("low"),
            uncertainty=_confirmed("low"),
            cost=_confirmed("low"),
            harm=_confirmed("low"),
        ),
    )
    ranked = operating_v4.select_next_candidates(db)["ranked_candidates"]
    positions = {item["candidate_id"]: item["rank"] for item in ranked}
    assert positions[f"bet:{known.id}"] < positions[f"bet:{discovery.id}"]


# 11. high-stake discovery can outrank low-stake convenient experiments.
def test_high_stake_discovery_outranks_low_stake_convenient(db):
    discovery = _discovery_candidate(
        db,
        assessments=_assessments(
            stake=_confirmed("high"),
            uncertainty=_confirmed("high"),
            evidence_potential=_confirmed("high"),
            cost=_confirmed("medium"),
            harm=_confirmed("low"),
        ),
    )
    known = _known_candidate(
        db,
        assessments=_assessments(
            stake=_confirmed("low"),
            uncertainty=_confirmed("low"),
            cost=_confirmed("low"),
            harm=_confirmed("low"),
        ),
    )
    ranked = operating_v4.select_next_candidates(db)["ranked_candidates"]
    positions = {item["candidate_id"]: item["rank"] for item in ranked}
    assert positions[f"bet:{discovery.id}"] < positions[f"bet:{known.id}"]


# 12. unassessed values do not become low silently.
def test_unassessed_never_becomes_low(db):
    left = _known_candidate(db, claim="left")
    right = _known_candidate(db, claim="right")
    ranked = operating_v4.select_next_candidates(db)["ranked_candidates"]
    by_id = {item["candidate_id"]: item for item in ranked}
    # Both fully unassessed: neither may win on a fabricated "low".
    assert by_id[f"bet:{left.id}"]["assessments"]["stake"]["level"] == "unassessed"
    assert by_id[f"bet:{right.id}"]["assessments"]["stake"]["level"] == "unassessed"
    # Tie broken deterministically by id, not by invented values.
    assert by_id[f"bet:{left.id}"]["rank"] != by_id[f"bet:{right.id}"]["rank"]


# 13. discovery finding becomes a known unknown only with valid provenance.
def test_finding_requires_provenance(db):
    bet = _discovery_candidate(db)
    with pytest.raises(ValueError, match="[Pp]rovenance"):
        discovery_selection.record_discovery_finding(
            db,
            discovery_bet_id=bet.id,
            finding_type="new_unknown",
            statement="We discovered X causes Y",
            proposed_unknown_question="Does X cause Y?",
        )


# 14. discovery finding preserves origin/provenance into the new known unknown.
def test_finding_preserves_provenance(db):
    bet = _discovery_candidate(db)
    ev = models.Evidence(claim="c", content="c", source="owner", source_type="firsthand")
    db.add(ev)
    db.commit()
    result = discovery_selection.record_discovery_finding(
        db,
        discovery_bet_id=bet.id,
        finding_type="new_unknown",
        statement="Discovered: owners route around formal discovery channels",
        evidence_ids=[ev.id],
        proposed_unknown_question="Do owners route around formal discovery channels?",
        cheapest_next_test="Ask three owners where they actually look",
        kill_rule="No owner names an informal channel",
    )
    assert result["finding_type"] == "new_unknown"
    new_id = result["new_candidate_id"]
    assert new_id is not None
    item = _ranked(db)[f"bet:{new_id}"]
    assert item["candidate_lane"] == "known_unknown"
    assert item["provisional_unknown"] is True
    assert item["origin_bet_id"] == bet.id
    assert item["origin_evidence_id"] == result["evidence_id"]
    assert "Do owners route around" in item["claim_or_question"]


# 15. no fabricated discovery candidate when source evidence is absent.
def test_no_fabricated_candidates_when_sources_empty(db):
    pool = discovery_selection.generate_discovery_candidates(db)
    assert pool["candidates"] == []
    assert set(pool["sources"]) == set(discovery_selection.DISCOVERY_SOURCES)
    assert all(entry["status"] == "unavailable" for entry in pool["sources"].values())


# 16. paused probe preserved as history; never privileged by selection.
def test_paused_probe_preserved_not_privileged(db):
    bet = operating_v4.create_bet(
        db,
        claim="Slow-reply probe",
        constraint="Response presence",
        test="One seller, one week",
        kill_criterion="No recovery",
        decision_rule="Recover >= 1 sale",
        skeptic_case="Sellers don't care",
        initial_status="paused",
    )
    item = _ranked(db)[f"bet:{bet.id}"]
    assert item["status"] == "paused"
    assert any("preserved as history" in blocker for blocker in item["gate_blockers"])
    selected = operating_v4.select_next_candidates(db)["selected_slate"]
    assert f"bet:{bet.id}" not in {item["candidate_id"] for item in selected}


# 17. existing three-live-Bet cap remains intact.
def test_three_live_bet_cap_intact(db):
    assert operating_v4.MAX_LIVE_BETS == 3
    for _ in range(3):
        discovery_selection.generate_discovery_candidates(db)
    result = operating_v4.select_next_candidates(db)
    assert result["available_live_slots"] <= 3
    assert len(result["selected_slate"]) <= result["available_live_slots"]


# 18. selection is read-only: it never promotes, executes, or mutates.
def test_selection_is_read_only(db):
    bet = _discovery_candidate(db)
    before = db.query(models.SubstrateEntity).count()
    operating_v4.select_next_candidates(db)
    after = db.query(models.SubstrateEntity).count()
    assert before == after
    db.refresh(bet)
    assert bet.attributes and '"candidate"' in bet.attributes


# 19. discovery candidates cannot autonomously execute consequential Actions.
def test_discovery_cannot_execute_action(db):
    bet = _discovery_candidate(
        db,
        assessments=_assessments(cost=_confirmed("low"), harm=_confirmed("low")),
    )
    operating_v4.select_next_candidates(db)
    actions = db.query(models.Action).count()
    assert actions == 0
    db.refresh(bet)
    assert "candidate" in (bet.attributes or "")


# Owner API: discovery endpoints carry the same owner-key protection.
class _StubRequest:
    def __init__(self, api_key=""):
        self.headers = {"X-API-Key": api_key} if api_key else {}


def test_discovery_api_requires_owner_key(db, monkeypatch):
    from app.api import operating_v4 as opv4_api
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "FORGE_API_KEY", "test-owner-key")
    with pytest.raises(HTTPException) as exc:
        opv4_api.get_discovery_candidates(request=_StubRequest(), db=db)
    assert exc.value.status_code == 401
    pool = opv4_api.get_discovery_candidates(request=_StubRequest("test-owner-key"), db=db)
    assert "candidates" in pool and "sources" in pool


# Generator grounding: parked domains yield horizon-escape specs; nothing invented.
def test_horizon_escape_grounded_in_parked_domains(db):
    parked = operating_v4.park_domain(db, "test-parked-domain", reason="outside focus")
    pool = discovery_selection.generate_discovery_candidates(db)
    escapes = [c for c in pool["candidates"] if c["source"] == "horizon_escape"]
    assert len(escapes) == 1
    assert "test-parked-domain" in escapes[0]["discovery_basis"]
    assert escapes[0]["provenance"] == "model-proposed"
    assert parked.id in escapes[0]["grounding_refs"]


def test_map_gap_grounded_in_uncovered_horizon_domains(db):
    operating_v4.set_current_watch_horizon(db, "test frontier")
    parked = operating_v4.park_domain(db, "uncovered-domain", reason="test")
    domain = operating_v4.unpark_domain(db, parked.id)
    pool = discovery_selection.generate_discovery_candidates(db)
    gaps = [c for c in pool["candidates"] if c["source"] == "map_gap"]
    assert any("uncovered-domain" in c["discovery_basis"] for c in gaps)
    assert domain.id in gaps[0]["grounding_refs"]


def test_capability_gap_grounded_in_unmet_capabilities(db):
    cap = models.ForgeCapability(
        capability_type="tool",
        name="test-unmet-capability",
        description="needed for investigation",
        status="proposed",
        owner_agent="owner",
    )
    db.add(cap)
    db.commit()
    pool = discovery_selection.generate_discovery_candidates(db)
    gaps = [c for c in pool["candidates"] if c["source"] == "capability_gap"]
    assert any("test-unmet-capability" in c["discovery_basis"] for c in gaps)


def test_no_material_discovery_records_without_new_candidate(db):
    bet = _discovery_candidate(db)
    result = discovery_selection.record_discovery_finding(
        db,
        discovery_bet_id=bet.id,
        finding_type="no_material_discovery",
        statement="Reviewed parked domain; nothing material found.",
        owner_confirmed=True,
    )
    assert result["finding_type"] == "no_material_discovery"
    assert result["new_candidate_id"] is None
    assert result["evidence_id"] is not None
