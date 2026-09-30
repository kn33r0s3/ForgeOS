"""
SCENARIO ENGINE — 2036 Civilization / Abundance Scenario Tracking (Phase 1)
=============================================================================

A SECONDARY, parallel domain to ForgeOS's primary Revenue Intelligence
mission (Signals -> Patterns -> Beliefs -> Opportunities -> Strategies ->
Execution -> Revenue). This module does not import, call, or modify any
part of that pipeline — opportunity_engine.py, money_engine.py,
execution_engine.py, autonomy_engine.py, and economic_intelligence.py are
all completely untouched. Confirmed by this file's own import list below:
it depends only on app.models.

Reuses ForgeOS's existing conventions rather than building parallel
infrastructure:

  - Evidence (models.py) — extended with a nullable scenario_prediction_id
    FK (v1.9) so one Evidence row can support/contradict EITHER a Belief
    OR a ScenarioPrediction, never both. Same table, same "direction"
    semantics, not a second evidence system.
  - ConfidenceEvent — same extension, for the append-only probability-
    change history a ScenarioPrediction accumulates, mirroring
    belief_engine.py's usage of ConfidenceEvent exactly.
  - economic_intelligence.py's "extract -> explainable score -> hard gate"
    SHAPE, reused here as classify_signal_domain() — a heuristic,
    non-LLM classifier for whether a Signal is robotics- or compute-
    relevant. Different vocabulary, same non-fabrication discipline.
  - worker.py's single existing scheduler — this module is called from
    forge_loop.run_cycle(); nothing here starts a second loop or agent.

THE CORE PRINCIPLE, enforced by construction, not just documented:
probability and confidence are two DIFFERENT numbers on ScenarioPrediction,
both defaulting to NULL ("insufficient evidence"), never invented to make
a dashboard look populated:

  probability = Forge's own estimated likelihood the predicted event
                 occurs — NOT the forecaster's own stated confidence
                 (a different thing, and one Musk rarely states a number
                 for at all)
  confidence  = Forge's confidence that the AVAILABLE EVIDENCE actually
                 supports the forecast — can be low even for a
                 probability Forge otherwise leans toward, if the
                 evidence behind it is thin

Reality > Prediction: a Forecaster's claim is stored as a testable
hypothesis, never as ForgeOS doctrine. ScenarioPrediction.status starts
"open" and only moves to "confirmed"/"failed" when real evidence resolves
it — exactly mirroring reality_memory.py's Prediction lifecycle for
Beliefs, applied to a forecaster's claim instead of a self-formed one.

PHASE 1 SCOPE (deliberately small): only "robotics" and "compute" have a
real classifier below. Every other domain from the full 16-domain matrix
(energy, land, governance, trust, ...) intentionally has none yet —
building all 16 now would mean building 14 empty dashboards. See the
README's v1.9 section for the full reasoning and continuation plan.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from typing import Optional

# --- The 6 mutually exclusive high-level scenarios ---------------------
#
# Evidence-first: every one starts at probability=None
# ("insufficient_evidence"), never an invented number — not even an
# equal 1/6 split, since even a computed-looking equal split would
# misrepresent how little is actually known yet.
DEFAULT_SCENARIOS = [
    {
        "code": "A",
        "name": "Extreme automation / abundance",
        "description": "AI and robotics rapidly displace most human labor; goods/services costs collapse; "
        "traditional employment and money become dramatically less central to daily life.",
    },
    {
        "code": "B",
        "name": "Partial automation / humans remain economically important",
        "description": "AI and robotics automate significant work, but humans remain economically necessary "
        "for a large share of tasks, judgment, and labor for the foreseeable future.",
    },
    {
        "code": "C",
        "name": "AI progress slows",
        "description": "Technical, economic, energy, or regulatory constraints slow AI/robotics capability "
        "growth well below current trajectories, delaying or preventing the other scenarios.",
    },
    {
        "code": "D",
        "name": "AI increases inequality / concentrates power",
        "description": "AI and robotics increase productivity and abundance in aggregate, but the economic "
        "gains concentrate among owners of capital/compute/robotics rather than being broadly distributed.",
    },
    {
        "code": "E",
        "name": "Abundance with persistent physical constraints",
        "description": "AI and robotics dramatically reduce the cost of intelligence and manufacturing, but "
        "physical scarcity (energy, land, raw materials, infrastructure) remains a binding constraint.",
    },
    {
        "code": "F",
        "name": "Unexpected technological or social outcome",
        "description": "The actual outcome does not resemble any of the above — a genuine placeholder for "
        "outcomes this scenario set failed to anticipate, rather than forcing reality into one of the other five.",
    },
]

# Phase 1's only two classified domains — see module docstring.
ROBOTICS_KEYWORDS = ["robot", "robots", "robotics", "humanoid", "optimus", "automat"]
COMPUTE_KEYWORDS = ["compute", "gpu", "gpus", "inference cost", "training cost", "chip", "chips", "data center", "datacenter"]


def utcnow():
    return datetime.now(timezone.utc)


def classify_signal_domain(text: str) -> Optional[str]:
    """
    Heuristic domain classifier — same "extract -> explainable score ->
    hard gate" shape as economic_intelligence.py, a different
    vocabulary. Returns "robotics", "compute", or None (unclassified) —
    never a guess. A signal matching both vocabularies returns whichever
    has more keyword hits; a genuine tie returns "robotics" (arbitrary
    but deterministic, documented here rather than silently
    inconsistent).
    """
    lowered = text.lower()
    robotics_hits = sum(1 for kw in ROBOTICS_KEYWORDS if kw in lowered)
    compute_hits = sum(1 for kw in COMPUTE_KEYWORDS if kw in lowered)
    if robotics_hits == 0 and compute_hits == 0:
        return None
    return "robotics" if robotics_hits >= compute_hits else "compute"


# --- Seeding (called from main.py/worker.py startup, same convention as ---
# --- source_manager.seed_default_sources() / money_engine.seed_default_---
# --- revenue_sources() / autonomy_engine.seed_default_policy()) -----------


def seed_default_scenarios(db: Session) -> None:
    """Insert the 6 default Scenario rows if they don't already exist.
    Idempotent — safe to call every startup."""
    for entry in DEFAULT_SCENARIOS:
        if db.query(models.Scenario).filter(models.Scenario.code == entry["code"]).first():
            continue
        db.add(
            models.Scenario(
                code=entry["code"],
                name=entry["name"],
                description=entry["description"],
                probability=None,
                probability_basis="insufficient_evidence",
            )
        )
    db.commit()


def seed_musk_forecaster_and_predictions(db: Session) -> None:
    """
    Seeds ONE Forecaster (Elon Musk) and TWO ScenarioPredictions
    attributed to him — both sourced from real web searches performed
    during implementation, never reconstructed from memory. Full
    citation trail lives in each row's source_url/source_name/
    source_date, and in the README's v1.9 section.

    The second prediction's exact wording could NOT be verified as a
    literal "university degrees will be irrelevant" claim — the
    verified quote is about future NECESSITY of college-taught SKILLS,
    not a categorical statement about degrees as credentials. The claim
    text stored is a close paraphrase of the VERIFIED quote;
    interpretation_note makes this distinction explicit rather than
    presenting the paraphrase as a verbatim quote.

    Idempotent: checks by (forecaster_id, claim) before inserting.
    """
    forecaster = db.query(models.Forecaster).filter(models.Forecaster.name == "Elon Musk").first()
    if not forecaster:
        forecaster = models.Forecaster(
            name="Elon Musk",
            description="CEO of Tesla and SpaceX. Tracked here as ONE forecaster among potentially many — "
            "his predictions are stored as testable hypotheses, not treated as authoritative. "
            "track_record_accuracy starts unset and is only ever computed from his own resolved predictions.",
        )
        db.add(forecaster)
        db.commit()
        db.refresh(forecaster)

    scenario_a = db.query(models.Scenario).filter(models.Scenario.code == "A").first()

    predictions = [
        {
            "claim": "Work will become optional within roughly 10-20 years as AI and robotics make human labor "
            "economically unnecessary for most goods and services.",
            "original_quote": '"My prediction is that work will be optional... It\'ll be like playing sports or a '
            'video game or something like that." "Maybe it\'s 10, 20 years or something like that."',
            "interpretation_note": None,
            "target_date": "~2035-2045 (Musk stated 'maybe 10, 20 years' as of Nov 2025)",
            "domain": "labor",
            "scenario_id": scenario_a.id if scenario_a else None,
            "source_url": "https://www.foxbusiness.com/economy/elon-musk-predicts-work-optional-coming-decades",
            "source_name": "Fox Business",
            "source_date": "2025-11-19",
            "reasoning": "Stated on-stage at the U.S.-Saudi Investment Forum (Nov 19, 2025), independently "
            "corroborated by Teslarati, Forbes, Gulf News, Tom's Guide, and Yahoo/AFP reporting the same event "
            "with matching quotes.",
        },
        {
            "claim": "Skills currently taught in college are likely to become economically unnecessary as AI and "
            "robotics advance, though Musk still supports college attendance for social/breadth reasons rather "
            "than job-skill training.",
            "original_quote": '"Will these skills be necessary in the future? Probably not, because we\'re gonna '
            'be in like a post-work society." "I don\'t think you have to go to college, but I think if you do, '
            'you just try to learn as much as possible across a wide range of subjects."',
            "interpretation_note": "IMPORTANT: this is NOT a verbatim claim that 'university degrees will be "
            "irrelevant.' The verified quote is about the future NECESSITY of college-taught SKILLS specifically, "
            "not a categorical statement about degrees as credentials. The claim text above is a paraphrase of "
            "the verified quote; the exact 'degree will be irrelevant' phrasing could not be independently "
            "verified and was NOT fabricated to fill this field.",
            "target_date": "Not specified by Musk for this specific claim",
            "domain": None,
            "scenario_id": None,
            "source_url": "https://www.yahoo.com/news/articles/elon-musk-says-dont-college-030112531.html",
            "source_name": "Yahoo Finance (citing the 'People By WTF' podcast with Nikhil Kamath)",
            "source_date": "2025-11 (podcast published November 2025)",
            "reasoning": "Independently corroborated by Business Insider/AOL reporting on the same podcast episode "
            "with matching quotes (\"AI and robotics is a supersonic tsunami... this is really going to be the "
            'most radical change that we\'ve ever seen").',
        },
    ]

    for entry in predictions:
        existing = (
            db.query(models.ScenarioPrediction)
            .filter(models.ScenarioPrediction.forecaster_id == forecaster.id, models.ScenarioPrediction.claim == entry["claim"])
            .first()
        )
        if existing:
            continue
        db.add(
            models.ScenarioPrediction(
                forecaster_id=forecaster.id,
                scenario_id=entry["scenario_id"],
                domain=entry["domain"],
                claim=entry["claim"],
                original_quote=entry["original_quote"],
                interpretation_note=entry["interpretation_note"],
                target_date=entry["target_date"],
                probability=None,
                confidence=None,
                reasoning=entry["reasoning"],
                source_url=entry["source_url"],
                source_name=entry["source_name"],
                source_date=entry["source_date"],
                status="open",
            )
        )
    db.commit()


def seed_phase1_indicators(db: Session) -> None:
    """
    2-3 Forge-generated (forecaster_id=None) ScenarioPredictions acting
    as Phase 1's tracked indicators — reusing ScenarioPrediction rather
    than a fourth new model, matching the explicit 3-model scope for
    this phase. Two (robotics, compute) have a real classifier
    (classify_signal_domain()) that WOULD populate them from Signals if
    any matching ones existed; one ("governance") intentionally has no
    classifier at all, included specifically to demonstrate the
    insufficient-evidence state honestly rather than only ever showing
    domains where something exists.
    """
    indicators = [
        {
            "domain": "robotics",
            "claim": "General-purpose humanoid robot cost and deployment rate are changing fast enough to make "
            "robotic labor broadly economically competitive with human labor.",
            "reasoning": "classify_signal_domain() exists and would tag matching Signals as 'robotics', but none "
            "have been observed and classified yet in this environment. Insufficient evidence, not zero interest.",
        },
        {
            "domain": "compute",
            "claim": "Inference cost per unit of AI capability is falling fast enough to make compute a "
            "shrinking bottleneck relative to other production inputs by 2036.",
            "reasoning": "classify_signal_domain() exists and would tag matching Signals as 'compute', but none "
            "have been observed and classified yet in this environment.",
        },
        {
            "domain": "governance",
            "claim": "Regulatory and governance frameworks are adapting fast enough to keep pace with AI/robotics "
            "capability growth — a precondition several scenarios above assume rather than examine directly.",
            "reasoning": "No classifier exists for this domain in Phase 1 at all — intentionally left "
            "unimplemented rather than building a shallow keyword list just to make this row look populated. "
            "One of the 14 domains from the original 16-domain matrix explicitly deferred to a later phase.",
        },
    ]
    for entry in indicators:
        existing = (
            db.query(models.ScenarioPrediction)
            .filter(
                models.ScenarioPrediction.forecaster_id.is_(None),
                models.ScenarioPrediction.domain == entry["domain"],
                models.ScenarioPrediction.claim == entry["claim"],
            )
            .first()
        )
        if existing:
            continue
        db.add(
            models.ScenarioPrediction(
                forecaster_id=None,
                scenario_id=None,
                domain=entry["domain"],
                claim=entry["claim"],
                original_quote=None,
                interpretation_note=None,
                target_date=None,
                probability=None,
                confidence=None,
                reasoning=entry["reasoning"],
                source_url=None,
                source_name=None,
                source_date=None,
                status="open",
            )
        )
    db.commit()


# --- forge_loop.run_cycle()'s new step (classification only, no seeding) ---


def run_scenario_engine_cycle(db: Session) -> dict:
    """
    The one new step appended to forge_loop.run_cycle(). Scans the 200
    most recent Signals for robotics/compute relevance
    (classify_signal_domain()) and links any matches as Evidence
    against the corresponding Phase 1 indicator ScenarioPrediction.

    Effectively a no-op when there are no eligible signals — verified
    standalone: with zero matching signals, this reads Signal rows,
    writes nothing, and returns signals_classified=0. Does NOT seed
    anything (seeding happens once at startup, same convention as
    source_manager.py/money_engine.py/autonomy_engine.py) and does NOT
    touch Belief, Opportunity, Strategy, Experiment, or any Revenue
    Intelligence table — reads Signal, writes Evidence only.
    """
    recent_signals = db.query(models.Signal).order_by(models.Signal.timestamp.desc()).limit(200).all()
    classified = 0

    for signal in recent_signals:
        domain = classify_signal_domain(signal.content)
        if domain is None:
            continue

        indicator = (
            db.query(models.ScenarioPrediction)
            .filter(models.ScenarioPrediction.forecaster_id.is_(None), models.ScenarioPrediction.domain == domain)
            .first()
        )
        if not indicator:
            continue

        already_linked = (
            db.query(models.Evidence)
            .filter(models.Evidence.scenario_prediction_id == indicator.id, models.Evidence.signal_id == signal.id)
            .first()
        )
        if already_linked:
            continue

        db.add(
            models.Evidence(
                belief_id=None,
                scenario_prediction_id=indicator.id,
                signal_id=signal.id,
                source=signal.source,
                content=signal.content,
                direction="supports",
                confidence=0.0,
                idempotency_key=f"scenario-prediction-signal:{indicator.id}:{signal.id}",
            )
        )
        classified += 1

    if classified:
        db.commit()

    return {"signals_reviewed": len(recent_signals), "signals_classified": classified}


# --- Read helpers for the API endpoint -----------------------------------


def get_scenario_overview(db: Session) -> dict:
    """Everything Phase 1 has: all Scenarios, all Forecasters, all
    ScenarioPredictions (with their evidence counts), for the one read
    endpoint. Read-only synthesis, same principle as world_model.py —
    computes nothing new, just assembles what already exists."""
    scenarios = db.query(models.Scenario).order_by(models.Scenario.code).all()
    forecasters = db.query(models.Forecaster).all()
    predictions = db.query(models.ScenarioPrediction).order_by(models.ScenarioPrediction.created_at.desc()).all()

    prediction_summaries = []
    for p in predictions:
        evidence_count = db.query(models.Evidence).filter(models.Evidence.scenario_prediction_id == p.id).count()
        prediction_summaries.append({"prediction": p, "evidence_count": evidence_count})

    return {
        "scenarios": scenarios,
        "forecasters": forecasters,
        "predictions": prediction_summaries,
    }
