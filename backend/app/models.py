"""
Forge Memory Engine — database models.

Four tables form the core loop of Forge:

Signal      -> raw observed information (a complaint, a note, a scraped post)
Pattern     -> repeated problems detected across multiple signals
Opportunity -> a business idea derived from a pattern (or a direct idea)
Experiment  -> a real-world test of an opportunity, and what was learned

This is intentionally a simple relational shape so it stays cheap to
run on SQLite today and maps cleanly onto Postgres later.
"""

from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Signal(Base):
    """A single piece of observed information fed into Forge.

    The Observer Engine (app/services/observer_engine.py) is what fills in
    signal_type, importance_score, processed, and tags automatically. Both
    the legacy POST /signals endpoint and the new POST /observer/observe
    endpoint write into this same table, so the Pattern Engine always sees
    one consistent pool of signals regardless of which door they came in.
    """

    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, default="manual")  # e.g. "manual", "reddit", "web"
    content = Column(Text, nullable=False)
    category = Column(String, nullable=True, index=True)  # e.g. "customer_service", "pricing"
    timestamp = Column(DateTime, default=utcnow, index=True)

    # --- Observer Engine fields ---
    signal_type = Column(String, nullable=True, default="problem", index=True)  # "problem" | "demand" | "observation"
    importance_score = Column(Float, nullable=False, default=0.0, index=True)  # 0-100
    processed = Column(Boolean, nullable=False, default=False)  # True once the Observer Engine has scored it
    tags = Column(Text, nullable=True)  # comma-separated tags, e.g. "restaurant,customer support,lost revenue"

    # --- Source Collector Framework fields ---
    reliability_score = Column(Float, nullable=False, default=50.0)  # snapshot of the source's Source.reliability_score at observe time
    freshness_score = Column(Float, nullable=False, default=100.0)  # 100 at observe time; decays conceptually with age (not auto-recomputed in v0.1)

    # --- Signal Quality Engine fields (v1.4) ---
    quality_score = Column(Float, nullable=True)  # 0-100, computed at observe time by signal_quality.py; NULL for signals observed before this migration ("not yet assessed", not "zero quality")
    quality_flags = Column(Text, nullable=True)  # comma-separated, e.g. "vague_no_specifics,incoherent_fragments"
    is_duplicate_of = Column(Integer, ForeignKey("signals.id"), nullable=True)  # set if this signal was recognized as a near-duplicate of an existing one
    canonical_url = Column(String, nullable=True, index=True)
    external_id = Column(String, nullable=True, index=True)
    identity_key = Column(String, nullable=True, unique=True)
    title = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    retrieved_at = Column(DateTime, default=utcnow, nullable=True)
    content_fingerprint = Column(String, nullable=True, index=True)
    source_type = Column(String, nullable=True, default="manual", index=True)  # "external" | "manual" | "seed" | "synthetic"
    provenance = Column(Text, nullable=True)
    collection_status = Column(String, nullable=False, default="observed")
    supersedes_signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)


class Pattern(Base):
    """A repeated problem/theme detected across multiple signals."""

    __tablename__ = "patterns"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    frequency = Column(Integer, default=0)  # number of signals supporting this pattern
    confidence_score = Column(Float, default=0.0)  # 0-100
    origin_signal_ids = Column(Text, nullable=True)  # comma-separated Signal ids this pattern was built from — its provenance
    created_at = Column(DateTime, default=utcnow)
    last_seen = Column(DateTime, default=utcnow)  # updated every time this same pattern re-detects, instead of inserting a duplicate row

    opportunities = relationship("Opportunity", back_populates="pattern")
    beliefs = relationship("Belief", back_populates="pattern")


class RareSignalAssessment(Base):
    """Persisted, explainable weak-signal assessment; scores are indicators."""

    __tablename__ = "rare_signal_assessments"

    id = Column(Integer, primary_key=True, index=True)
    cluster_key = Column(String, nullable=False, index=True)
    label = Column(Text, nullable=False)
    signal_ids = Column(Text, nullable=False)
    frequency = Column(Integer, nullable=False, default=0)
    prior_frequency = Column(Integer, nullable=False, default=0)
    recent_frequency = Column(Integer, nullable=False, default=0)
    velocity = Column(Float, nullable=False, default=0.0)
    acceleration = Column(Float, nullable=False, default=0.0)
    source_diversity = Column(Float, nullable=False, default=0.0)
    novelty = Column(Float, nullable=False, default=0.0)
    specificity = Column(Float, nullable=False, default=0.0)
    pain_intensity = Column(Float, nullable=False, default=0.0)
    solution_scarcity = Column(Float, nullable=False, default=0.0)
    economic_relevance = Column(Float, nullable=False, default=0.0)
    freshness = Column(Float, nullable=False, default=0.0)
    recurrence = Column(Float, nullable=False, default=0.0)
    geographic_spread = Column(Float, nullable=False, default=0.0)
    language_spread = Column(Float, nullable=False, default=0.0)
    score = Column(Float, nullable=False, default=0.0, index=True)
    status = Column(String, nullable=False, default="DETECTED")
    explanation = Column(JSON, nullable=False, default=dict)
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    research_question_id = Column(Integer, ForeignKey("research_questions.id"), nullable=True)
    first_seen = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    events = relationship("RareSignalEvent", back_populates="assessment", cascade="all, delete-orphan")


class RareSignalEvent(Base):
    """Append-only history of meaningful weak-signal changes."""

    __tablename__ = "rare_signal_events"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("rare_signal_assessments.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    assessment = relationship("RareSignalAssessment", back_populates="events")


class Opportunity(Base):
    """A business opportunity, optionally derived from a Pattern."""

    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)  # which Goal (if any) this opportunity serves

    problem = Column(Text, nullable=False)
    target_customer = Column(Text, nullable=True)
    solution = Column(Text, nullable=True)
    business_model = Column(Text, nullable=True)
    pricing_idea = Column(Text, nullable=True)
    market_analysis = Column(Text, nullable=True)
    mvp_plan = Column(Text, nullable=True)
    validation_plan = Column(Text, nullable=True)
    difficulty = Column(String, nullable=True)  # "low" | "medium" | "high"
    score = Column(Float, default=0.0)  # 0-100 opportunity score
    created_at = Column(DateTime, default=utcnow)

    # --- Money Engine fields (v1.1) ---
    # All evidence-gated: confidence/uncertainty fields start at the
    # "nothing known yet" end (0 confidence, 100 uncertainty) rather
    # than an invented neutral middle, and revenue/price fields stay
    # NULL until a real Experiment records them — money_engine.py never
    # fabricates a number here. See money_engine.py's module docstring.
    customer_segment = Column(Text, nullable=True)
    economic_consequence = Column(Text, nullable=True)  # the cost of the problem to the customer, if known
    offer = Column(Text, nullable=True)
    acquisition_path = Column(Text, nullable=True)  # how a customer would actually be reached
    estimated_price = Column(Float, nullable=True)  # never auto-set; only from explicit input or a tested price
    estimated_revenue = Column(Float, nullable=True)  # updated only from REAL recorded Experiment.revenue, never guessed
    problem_evidence_signal_ids = Column(Text, nullable=True)  # comma-separated Signal ids evidencing the problem exists
    willingness_evidence_ids = Column(Text, nullable=True)  # comma-separated Experiment ids evidencing willingness to pay
    market_confidence = Column(Float, nullable=False, default=0.0)  # 0-100, starts at 0 (unknown), moves only with evidence
    revenue_confidence = Column(Float, nullable=False, default=0.0)  # 0-100, starts at 0 (no revenue evidence yet)
    implementation_difficulty = Column(Float, nullable=True)  # 0-100, higher = harder; null until estimated
    acquisition_difficulty = Column(Float, nullable=True)  # 0-100, higher = harder
    uncertainty = Column(Float, nullable=False, default=100.0)  # 0-100, starts at MAX (nothing tested yet)
    competition_evidence = Column(Text, nullable=True)
    expected_value = Column(Float, nullable=True)  # never fabricated — see money_engine.score_opportunity()
    status = Column(String, nullable=False, default="identified")  # "identified" | "validating" | "validated" | "invalidated" | "abandoned"
    owner_priority = Column(Float, nullable=False, default=50.0)  # 0-100, how much the owner cares about pursuing THIS opportunity specifically
    updated_at = Column(DateTime, default=utcnow)

    # --- Lifecycle flag ---
    no_meaningful_change = Column(Boolean, nullable=False, default=False)
    identity_key = Column(String, nullable=True, index=True)

    # --- Money Engine fields, v1.2 ---
    # ALL of these are estimates/projections, never facts — see
    # money_engine.classify_evidence(), which reports each one's
    # epistemic status (observed/inferred/estimated/unknown) rather
    # than letting a number's mere presence imply certainty.
    monetization_model = Column(String, nullable=True)  # "service" | "productized_service" | "saas" | "digital_product" | "lead_generation" | "affiliate" | "marketplace" | "subscription" | "consulting" | "automation_service" | "unknown" — inferred from evidence, never asserted
    time_to_first_revenue_days = Column(Float, nullable=True)  # ESTIMATED — how long until this could plausibly produce a first dollar
    estimated_revenue_30d = Column(Float, nullable=True)  # ESTIMATED projection, not a fact
    estimated_revenue_90d = Column(Float, nullable=True)  # ESTIMATED projection, not a fact
    estimated_effort_hours = Column(Float, nullable=True)  # ESTIMATED
    estimated_startup_cost = Column(Float, nullable=True)  # ESTIMATED
    revenue_source_id = Column(Integer, ForeignKey("revenue_sources.id"), nullable=True)  # a REAL, known payout mechanism this opportunity would use, if identified — see RevenueSource below

    # --- Economic Intelligence fields (v1.8) ---
    economic_evidence_summary = Column(Text, nullable=True)  # frozen, human-readable explanation of WHY this became an opportunity — set once by opportunity_engine.generate_opportunity_from_pattern_if_economic(), never regenerated

    pattern = relationship("Pattern", back_populates="opportunities")
    experiments = relationship("Experiment", back_populates="opportunity")
    # relationship to Evidence (many-to-one from Evidence side)
    evidence_items = relationship("Evidence", back_populates="opportunity", cascade="all, delete-orphan")
    history = relationship("OpportunityEvent", back_populates="opportunity", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="opportunity")


class OpportunityEvent(Base):
    """Append-only record of meaningful opportunity changes."""

    __tablename__ = "opportunity_events"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    event_key = Column(String, nullable=False, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    opportunity = relationship("Opportunity", back_populates="history")

class WorkerTask(Base):
    """Persistent task representing a worker's unit of work.

    Tracks identity, status, priority, inputs/outputs, timestamps, attempts, and errors.
    """

    __tablename__ = "worker_tasks"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    worker_type = Column(String, nullable=False)  # e.g. discovery, research, builder, etc.
    task_name = Column(String, nullable=False)   # short description of the work to do
    status = Column(String, nullable=False, default="queued")  # queued, running, completed, failed, blocked
    priority = Column(Integer, nullable=False, default=0)  # higher => higher priority
    inputs = Column(JSON, nullable=True)        # JSON blob consumed by the worker
    outputs = Column(JSON, nullable=True)       # JSON blob produced by the worker
    evidence = Column(JSON, nullable=True)      # Any evidence collected/associated
    dependencies = Column(JSON, nullable=True)  # List of prerequisite task IDs
    worker_id = Column(String, nullable=True)   # Identity of the worker executing it
    role = Column(String, nullable=True)        # Role context for the worker
    error = Column(Text, nullable=True)        # error message if failed
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    next_run_at = Column(DateTime, nullable=True)  # for retries / delayed execution



class Experiment(Base):
    """A real-world test run against an Opportunity, and its outcome.

    Doubles as Forge's Revenue Experiment (v1.1, Money Engine) AND its
    Execution Action (v1.5, Money Execution Engine) — reused rather
    than duplicated, since a revenue test IS an executable action
    against an opportunity, and an execution action's result IS what
    hypothesis/expected_result/revenue/conversions/confidence_change
    already captured. The original action/result/lesson fields are
    untouched and the old POST /experiments endpoint keeps working
    exactly as before. Immutable once `result` is set — record_revenue_
    result() / execution_engine.record_action_result() both refuse to
    edit a completed row; a changed test creates a NEW Experiment
    instead."""

    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    action = Column(Text, nullable=False)
    result = Column(Text, nullable=True)
    lesson = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # --- Research-first provenance ---
    source_analyze_id = Column(Integer, nullable=True, index=True)
    source_signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True, index=True)
    source_research_question_id = Column(
        Integer, ForeignKey("research_questions.id"), nullable=True, index=True
    )
    source_research_task_ids = Column(JSON, nullable=True)  # list[int]

    # --- Explicit authorization state ---
    authorization_status = Column(String, nullable=False, default="require_approval", index=True)
    authorization_reason = Column(Text, nullable=True)
    authorized_by = Column(String, nullable=True)
    authorized_at = Column(DateTime, nullable=True)

    # --- Canonical execution state ---
    execution_status = Column(String, nullable=False, default="proposed", index=True)
    executed_at = Column(DateTime, nullable=True)
    execution_notes = Column(Text, nullable=True)

    # --- Actual external response ---
    response_received = Column(String, nullable=False, default="none", index=True)
    response_raw = Column(Text, nullable=True)
    response_received_at = Column(DateTime, nullable=True)

    # --- Actual revenue (truth-controlled) ---
    revenue_amount = Column(Float, nullable=False, default=0.0)
    revenue_currency = Column(String, nullable=False, default="USD")
    revenue_recorded_at = Column(DateTime, nullable=True)

    # --- Learning linkage ---
    learning_event_id = Column(Integer, ForeignKey("learning_events.id"), nullable=True, index=True)
    next_decision = Column(Text, nullable=True)

    # --- Revenue Experiment fields (v1.1) ---
    hypothesis = Column(Text, nullable=True)  # e.g. "Restaurants will pay $99/mo for an AI answering service"
    expected_result = Column(Text, nullable=True)
    revenue = Column(Float, nullable=True)  # actual $ recorded from a completed test — never a guess
    conversions = Column(Integer, nullable=True)  # e.g. how many of N prospects said yes
    confidence_change = Column(Float, nullable=True)  # set once when result is recorded, never edited after

    # --- Execution lifecycle fields (v1.5, Money Execution Engine) ---
    # These turn a "revenue experiment row" into a trackable executable
    # action with real state — predicted -> attempted -> completed ->
    # verified — and an explicit owner-approval gate for anything that
    # involves spending or commitment. See execution_engine.py.
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)  # which Strategy this action executes, if any
    option_id = Column(Integer, ForeignKey("options.id"), nullable=True)
    action_type = Column(String, nullable=True)  # "customer_interview" | "outreach" | "offer" | "paid_pilot" | "service_delivery" | "revenue_experiment" | "follow_up" | "validate_pricing" | "build_mvp"
    status = Column(String, nullable=False, default="planned")  # "planned" | "ready" | "in_progress" | "completed" | "abandoned" | "blocked" (v1.7)
    execution_mode = Column(String, nullable=True)  # "executable_locally" | "requires_owner_action" | "requires_external_integration" — the real-world boundary; Forge never claims to have done something it can't actually do
    requires_owner_approval = Column(Boolean, nullable=False, default=False)  # True for spending/commitment-bearing action types — cannot start without approved_at set
    approved_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    costs = Column(Float, nullable=True)  # actual $ spent — never a guess, same discipline as revenue
    required_inputs = Column(Text, nullable=True)  # free text: what the owner/Forge needs before this can run, e.g. "list of 20 target businesses"

    # --- Autonomy Policy fields (v1.7) ---
    # Computed ONCE at creation and frozen — "the decision must be
    # explainable" and "never silently overwrite historical results."
    # See autonomy_engine.py.
    estimated_cost = Column(Float, nullable=True)  # a stated estimate at proposal time — distinct from `costs` (the real, recorded figure); never treated as a fact
    risk_score = Column(Float, nullable=True)  # 0-100, computed transparently at creation — see autonomy_engine.compute_risk_score()
    policy_decision = Column(String, nullable=True)  # "allow" | "require_approval" | "block" — frozen at creation
    policy_reason = Column(Text, nullable=True)  # human-readable, generated from the same factors used to decide — not an LLM explanation
    attempt_number = Column(Integer, nullable=False, default=1)  # which attempt this is for this (opportunity, action_type) pair — used for retry-limit enforcement

    # Domain isolation for execution safety (revenue / scenario / other).
    domain = Column(String, nullable=False, default="revenue", index=True)  # "revenue" | "scenario" | "other"
    execution_allowed = Column(Boolean, nullable=False, default=False)  # fail-closed default
    data_scope = Column(String, nullable=False, default="REAL", index=True)  # REAL | SANDBOX; sandbox results never count as business traction

    # --- Experiments registry (2026-10-05) ---
    # OBSERVATION: may run in parallel, no human contact.
    # CONVERSATION: batches of 5, owner approval required per batch.
    # INTERVENTION: at most ONE active at a time (see intervention_gate).
    experiment_kind = Column(String, nullable=True, index=True)
    five_fields_json = Column(Text, nullable=True)  # JSON: reality, possibility, constraint, constraint_state, intervention, outcome

    opportunity = relationship("Opportunity", back_populates="experiments")


# ---------------------------------------------------------------------
# Reality / Belief layer
#
# These five tables are new in this version and are entirely additive —
# no existing table's shape changes, so nothing above this line needed
# a migration. Together they implement:
#
#   Pattern -> Belief (a hypothesis about how reality works)
#            -> Reality Checker re-scores Belief.confidence_score against
#               new signals over time
#            -> BeliefExperiment tests a Belief in the real world and
#               feeds its result back into confidence_score
#   ResearchQuestion -> generated by the Curiosity Engine for weak/
#                        contradicting/unexplored areas of knowledge
#   ResearchTask      -> generated by the Research Planner from a
#                         ResearchQuestion; not yet executed by any
#                         collector (those are future work)
#   Source             -> tracks how reliable each observation source is,
#                          so evidence from different sources can be
#                          weighted differently later
# ---------------------------------------------------------------------


class Belief(Base):
    """A hypothesis about how reality works, formed from one or more
    Patterns and updated over time as new evidence appears.

    A record may be called a hypothesis only when it carries all four
    qualifying fields: actor_segment, need_pain, give_up, and at least
    one supporting signal. Anything else is an observation — stored,
    never deleted, but never surfaced publicly as a hypothesis.
    """

    __tablename__ = "beliefs"

    id = Column(Integer, primary_key=True, index=True)
    statement = Column(Text, nullable=False, unique=True)
    pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)  # the Pattern this belief was originally formed from — its causal origin, never overwritten once set
    merged_into_id = Column(Integer, ForeignKey("beliefs.id"), nullable=True, index=True)
    supporting_signal_ids = Column(Text, nullable=True)  # comma-separated Signal ids
    confidence_score = Column(Float, nullable=False, default=50.0, index=True)  # 0-100
    created_at = Column(DateTime, default=utcnow)
    last_updated = Column(DateTime, default=utcnow)
    # Hypothesis qualification (additive, 2026-10-04): a keyword bag is an
    # observation until someone records who it is about, what they need,
    # what they would give up, and points at evidence.
    label = Column(String(32), nullable=False, default="observation", index=True)
    actor_segment = Column(Text, nullable=True)  # who: the actor/segment this is about
    need_pain = Column(Text, nullable=True)  # the stated need or pain
    give_up = Column(Text, nullable=True)  # what the actor would give up: money/time/behavior
    relabel_reason = Column(Text, nullable=True)  # why the label changed; archive trail, never deleted

    pattern = relationship("Pattern", back_populates="beliefs")


class ResearchQuestion(Base):
    """Something Forge has decided it wants to understand better —
    generated by the Curiosity Engine from low-confidence beliefs or
    patterns with no belief formed yet."""

    __tablename__ = "research_questions"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False, unique=True)
    priority_score = Column(Float, nullable=False, default=50.0)  # 0-100
    status = Column(String, nullable=False, default="open")  # "open" | "planned" | "closed"
    source_pattern_id = Column(Integer, ForeignKey("patterns.id"), nullable=True)
    source_belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=True)
    source_claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    source_rare_signal_id = Column(Integer, ForeignKey("rare_signal_assessments.id"), nullable=True, index=True)
    research_plan = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class ResearchTask(Base):
    """A concrete task derived from a ResearchQuestion by the Research
    Planner, executed by collector_runner (begin/run/finish state machine).
    Idempotent per (question_id, source, query) with a backfilled unique
    idempotency key (uq_research_tasks_idempotency_key)."""

    __tablename__ = "research_tasks"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("research_questions.id"), nullable=False)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    idempotency_key = Column(String, nullable=True)
    source = Column(String, nullable=False)  # e.g. "reddit", "github", "news"
    query = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="planned")  # planned | running | completed | needs_research | failed
    objective = Column(Text, nullable=True)
    plan = Column(JSON, nullable=True)
    tools_used = Column(JSON, nullable=True)
    evidence_ids = Column(Text, nullable=True)
    claims = Column(JSON, nullable=True)
    judgments = Column(JSON, nullable=True)
    contradictions = Column(JSON, nullable=True)
    remaining_questions = Column(JSON, nullable=True)
    results = Column(JSON, nullable=True)
    errors = Column(JSON, nullable=True)
    current_step = Column(String, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    question = relationship("ResearchQuestion")
    steps = relationship("ResearchTaskStep", back_populates="task", cascade="all, delete-orphan")
    history = relationship("ResearchTaskEvent", back_populates="task", cascade="all, delete-orphan")


class ResearchTaskStep(Base):
    __tablename__ = "research_task_steps"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("research_tasks.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    position = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="pending")
    tool_name = Column(String, nullable=True)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("ResearchTask", back_populates="steps")


class ResearchTaskEvent(Base):
    __tablename__ = "research_task_events"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("research_tasks.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    step_name = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    task = relationship("ResearchTask", back_populates="history")


class ToolUsageEvent(Base):
    """Observed performance of one tool invocation; never a fabricated score."""

    __tablename__ = "tool_usage_events"

    id = Column(Integer, primary_key=True, index=True)
    tool_name = Column(String, nullable=False, index=True)
    query = Column(Text, nullable=True)
    research_task_id = Column(Integer, ForeignKey("research_tasks.id"), nullable=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    result_count = Column(Integer, nullable=True)
    useful_result_count = Column(Integer, nullable=True)
    novel_result_count = Column(Integer, nullable=True)
    verified_result_count = Column(Integer, nullable=True)
    duplicate_result_count = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False, default=False)
    failure_kind = Column(String, nullable=True)
    cost = Column(Float, nullable=True)
    event_key = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class SourceUsageEvent(Base):
    """Observed usefulness of one source within one research invocation."""

    __tablename__ = "source_usage_events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=True)
    query = Column(Text, nullable=True)
    research_task_id = Column(Integer, ForeignKey("research_tasks.id"), nullable=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    result_count = Column(Integer, nullable=True)
    useful_evidence_count = Column(Integer, nullable=True)
    novel_evidence_count = Column(Integer, nullable=True)
    corroborated_evidence_count = Column(Integer, nullable=True)
    contradicted_claim_count = Column(Integer, nullable=True)
    duplicate_result_count = Column(Integer, nullable=True)
    freshness = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False, default=False)
    failure_kind = Column(String, nullable=True)
    event_key = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class IntelligenceCacheEntry(Base):
    """Durable local cache with deterministic identity and freshness metadata."""

    __tablename__ = "intelligence_cache_entries"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, nullable=False, index=True)
    object_type = Column(String, nullable=False, index=True)
    input_fingerprint = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    fetched_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    stale_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="current")  # current | stale | invalidated
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)


class BeliefExperiment(Base):
    """A real-world test of a Belief (distinct from the existing
    Experiment table, which tests Opportunities). Recording a result
    feeds confidence_change back into the linked Belief."""

    __tablename__ = "belief_experiments"

    id = Column(Integer, primary_key=True, index=True)
    belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=False)
    hypothesis = Column(Text, nullable=False)
    method = Column(Text, nullable=False)
    result = Column(Text, nullable=True)
    confidence_change = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="planned")  # "planned" | "completed"
    created_at = Column(DateTime, default=utcnow)


class Source(Base):
    """Tracks how reliable each observation source has been, so
    evidence can eventually be weighted rather than treated equally.
    Startup stores one unmeasured baseline. reliability_score moves
    when a Prediction resolves."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)  # "manual", "reddit", "github"...
    type = Column(String, nullable=True)  # "human" | "discussion" | "code" | "media" | "general" | "research"
    reliability_score = Column(Float, nullable=False, default=50.0)  # 0-100
    last_checked = Column(DateTime, nullable=True)
    lifespan = Column(String, nullable=True)  # "permanent" | "long" | "medium" | "short" | "variable"
    url = Column(String, nullable=True)  # default feed/endpoint for this source, if any — collectors read this via source_manager.get_source_url()


class SourceFetchGate(Base):
    """Durable per-source throttle shared by workers and API instances."""

    __tablename__ = "source_fetch_gates"

    registry_id = Column(String, primary_key=True)
    last_reserved_at = Column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------
# Reality Memory
#
# Evidence persists what the Reality Checker finds (previously only
# returned ephemerally in the API response) so it can be inspected
# later and so source reliability adjustments have something to look
# back on. Prediction is a testable claim generated from a confident
# Belief; resolving it (confirmed/failed) is what actually closes the
# "learn from being wrong" loop — see reality_memory.py.
# ---------------------------------------------------------------------


class Evidence(Base):
    """Evidence linking a raw Signal to an Opportunity, Belief, or ScenarioPrediction."""

    __tablename__ = "evidence"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)
    source = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    direction = Column(String, nullable=True)
    provenance_hash = Column(String, nullable=True, index=True)
    # Nullable while old evidence is preserved unchanged; new idempotent
    # writers populate this unique key instead of relying on legacy hashes.
    idempotency_key = Column(String, nullable=True, unique=True)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utcnow)
    scenario_prediction_id = Column(Integer, ForeignKey("scenario_predictions.id"), nullable=True)
    canonical_url = Column(String, nullable=True, index=True)
    external_id = Column(String, nullable=True, index=True)
    title = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    retrieved_at = Column(DateTime, default=utcnow, nullable=True)
    content_fingerprint = Column(String, nullable=True, index=True)
    provenance = Column(Text, nullable=True)
    collection_status = Column(String, nullable=False, default="collected")
    # Universal-substrate evidence fields. Legacy claim/opportunity links stay
    # intact; these fields attach evidence to a substrate entity or relation.
    subject_kind = Column(String, nullable=True)
    subject_id = Column(Integer, nullable=True, index=True)
    claim = Column(Text, nullable=True)
    support_level = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=True)
    # Substrate interpretations are kept separate from historic raw fields.
    # In particular, legacy confidence is commonly 0–100 and must not be
    # rescaled or overwritten during substrate migration.
    substrate_source = Column(String, nullable=True)
    substrate_confidence = Column(Float, nullable=True)
    substrate_provenance = Column(Text, nullable=True)

    signal = relationship("Signal")
    opportunity = relationship("Opportunity", back_populates="evidence_items")
    claim_links = relationship("EvidenceRelationship", back_populates="evidence", cascade="all, delete-orphan")


class Claim(Base):
    """A traceable statement with an explicit epistemic state."""

    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    statement = Column(Text, nullable=False)
    normalized_statement = Column(String, nullable=False, index=True)
    epistemic_state = Column(String, nullable=False, default="observed")
    confidence = Column(Float, nullable=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True, index=True)
    outcome_id = Column(Integer, ForeignKey("outcomes.id"), nullable=True, index=True)
    provenance = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    opportunity = relationship("Opportunity", back_populates="claims")
    evidence_links = relationship("EvidenceRelationship", back_populates="claim", cascade="all, delete-orphan")
    judgments = relationship("Judgment", back_populates="claim")


class EvidenceRelationship(Base):
    """Typed, de-duplicated legacy link with an optional substrate relation ref."""

    __tablename__ = "evidence_relationships"

    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True, index=True)
    outcome_id = Column(Integer, ForeignKey("outcomes.id"), nullable=True, index=True)
    judgment_id = Column(Integer, ForeignKey("judgments.id"), nullable=True, index=True)
    network_connection_id = Column(
        Integer,
        ForeignKey("network_connections.id"),
        nullable=True,
        index=True,
    )
    relation_type = Column(String, nullable=False)
    relation_key = Column(String, nullable=False, index=True)
    # New link writes use a unique key. Historical relation_key values remain
    # untouched because old databases may contain duplicates.
    idempotency_key = Column(String, nullable=True, unique=True)
    substrate_relation_id = Column(Integer, ForeignKey("relations.id"), nullable=True, unique=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    evidence = relationship("Evidence", back_populates="claim_links")
    claim = relationship("Claim", back_populates="evidence_links")
    judgment = relationship("Judgment", back_populates="evidence_links")
    network_connection = relationship("NetworkConnection")


class TypeRegistry(Base):
    """Open vocabulary registry; new domains add typed rows, not ORM tables."""

    __tablename__ = "type_registry"
    __table_args__ = (
        CheckConstraint(
            "category IN ('entity_type','relation_type','event_type','capability_type')",
            name="ck_type_registry_category",
        ),
        CheckConstraint("status IN ('proposed','active','deprecated')", name="ck_type_registry_status"),
        UniqueConstraint("category", "type_name", name="uq_type_registry_category_name"),
    )

    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False)
    type_name = Column(String, nullable=False)
    schema_json = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    owner_agent = Column(String, nullable=False)
    status = Column(String, nullable=False, default="proposed")
    # Append-only lifecycle decisions (activation/deprecation actor, rationale,
    # and evidence/process reference). Existing rows remain readable.
    status_evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class SubstrateEntity(Base):
    """Generic identity and attributes for canonical or newly represented things."""

    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint("status IN ('active','archived','merged')", name="ck_entities_status"),
        CheckConstraint(
            "identity_state IN ('candidate','corroborated','canonical')",
            name="ck_entities_identity_state",
        ),
    )

    id = Column(Integer, primary_key=True)
    entity_type = Column(String, nullable=False, index=True)
    display_name = Column(Text, nullable=False)
    attributes = Column(Text, nullable=False, default="{}")
    # Stable adapter identity prevents one source record from creating multiple
    # substrate wrappers. Nullable unique keys keep hand-created candidates open.
    identity_key = Column(String, nullable=True, unique=True)
    source_system = Column(String, nullable=True, index=True)
    source_id = Column(String, nullable=True)
    canonical_identifier = Column(Text, nullable=True, index=True)
    normalized_identity = Column(Text, nullable=True, index=True)
    identity_state = Column(String, nullable=False, default="candidate", index=True)
    identity_uncertainty = Column(Text, nullable=True)
    identity_provenance = Column(Text, nullable=True)
    merged_into_id = Column(Integer, ForeignKey("entities.id"), nullable=True, index=True)
    status = Column(String, nullable=False, default="active", index=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class WorldRelation(Base):
    """Open typed relationship between two substrate entities."""

    __tablename__ = "relations"
    __table_args__ = (
        CheckConstraint("direction IN ('directed','bidirectional')", name="ck_relations_direction"),
        CheckConstraint(
            "truth_state IN ('possible','hypothesized','tested','supported','refuted','unknown')",
            name="ck_relations_truth_state",
        ),
        CheckConstraint("strength IS NULL OR (strength >= 0 AND strength <= 1)", name="ck_relations_strength"),
        CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from", name="ck_relations_validity"),
    )

    id = Column(Integer, primary_key=True)
    from_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    to_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    relation_type = Column(String, nullable=False, index=True)
    attributes = Column(Text, nullable=False, default="{}")
    direction = Column(String, nullable=False, default="directed")
    strength = Column(Float, nullable=True)
    truth_state = Column(String, nullable=False, default="hypothesized", index=True)
    idempotency_key = Column(String, nullable=True, unique=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    from_entity = relationship("SubstrateEntity", foreign_keys=[from_entity_id])
    to_entity = relationship("SubstrateEntity", foreign_keys=[to_entity_id])


class WorldEvent(Base):
    """A typed occurrence tied to an entity, relation, or the world generally."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "entity_id IS NULL OR relation_id IS NULL",
            name="ck_events_single_subject",
        ),
    )

    id = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True, index=True)
    relation_id = Column(Integer, ForeignKey("relations.id"), nullable=True, index=True)
    payload = Column(Text, nullable=False, default="{}")
    source = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=True, unique=True)
    occurred_at = Column(DateTime, nullable=False, default=utcnow)


class ForgeBotLeadContact(Base):
    """Private, consent-scoped contact details for Forge Bot inquiries only."""

    __tablename__ = "forge_bot_lead_contacts"
    __table_args__ = (
        CheckConstraint(
            "preferred_channel IN ('email','phone')",
            name="ck_forge_bot_leads_preferred_channel",
        ),
        CheckConstraint(
            "consent_granted = true",
            name="ck_forge_bot_leads_consent_required",
        ),
        CheckConstraint(
            "evidence_class IN ('REAL','TEST')",
            name="ck_forge_bot_leads_evidence_class",
        ),
    )

    id = Column(Integer, primary_key=True)
    public_ref = Column(String(32), nullable=False, unique=True, index=True)
    email = Column(String(254), nullable=True)
    normalized_email = Column(String(254), nullable=True, unique=True)
    phone = Column(String(32), nullable=True)
    normalized_phone = Column(String(15), nullable=True, unique=True)
    email_suppression_hmac = Column(String(64), nullable=True, unique=True)
    phone_suppression_hmac = Column(String(64), nullable=True, unique=True)
    manage_token_hash = Column(String(64), nullable=True, unique=True)
    preferred_channel = Column(String(16), nullable=False)
    destination = Column(String(120), nullable=True)
    course = Column(String(160), nullable=True)
    timeline = Column(String(120), nullable=True)
    budget_minimum = Column(Integer, nullable=True)
    budget_maximum = Column(Integer, nullable=True)
    stage = Column(String(32), nullable=False, default="READY_FOR_OWNER_REVIEW")
    evidence_class = Column(String(8), nullable=False, default="REAL")
    consent_granted = Column(Boolean, nullable=False, default=True)
    consent_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    consent_purpose = Column(
        String(80), nullable=False, default="respond_to_forge_bot_inquiry"
    )
    consent_provenance = Column(
        String(80), nullable=False, default="forge_bot_web_form_v1"
    )
    opted_out = Column(Boolean, nullable=False, default=False)
    opted_out_at = Column(DateTime(timezone=True), nullable=True)
    erased_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class ForgeBotIntakeRateLimit(Base):
    """Privacy-preserving hourly intake counter keyed by a visitor HMAC."""

    __tablename__ = "forge_bot_intake_rate_limits"

    visitor_hash = Column(String(64), primary_key=True)
    request_count = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class OpForgeBotResponseAuthorization(Base):
    """Singleton operational projection for owner-authorized lead responses."""

    __tablename__ = "op_forge_bot_response_authorization"
    __table_args__ = (
        CheckConstraint(
            "selected_channel IS NULL OR selected_channel IN ('email','phone')",
            name="ck_forge_bot_response_selected_channel",
        ),
        CheckConstraint(
            "opt_out_boundary = 'permanent_suppression'",
            name="ck_forge_bot_response_opt_out_boundary",
        ),
        CheckConstraint(
            "escalation_boundary = 'owner_confirmation_required_for_exceptions'",
            name="ck_forge_bot_response_escalation_boundary",
        ),
    )

    id = Column(Integer, primary_key=True)
    selected_channel = Column(String(16), nullable=True)
    channel_authorized = Column(Boolean, nullable=False, default=False)
    template_ref = Column(String(200), nullable=True)
    template_authorized = Column(Boolean, nullable=False, default=False)
    consent_required = Column(Boolean, nullable=False, default=True)
    opt_out_boundary = Column(
        String(40), nullable=False, default="permanent_suppression"
    )
    escalation_boundary = Column(
        String(64),
        nullable=False,
        default="owner_confirmation_required_for_exceptions",
    )
    external_send_authorized = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ForgeCapability(Base):
    """A reusable ability Forge proposes, builds, tests, then activates."""

    __tablename__ = "capabilities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed','building','tested','active','deprecated')",
            name="ck_capabilities_status",
        ),
        CheckConstraint("status != 'active' OR test_ref IS NOT NULL", name="ck_capabilities_active_test_ref"),
    )

    id = Column(Integer, primary_key=True)
    capability_type = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="proposed", index=True)
    spec_ref = Column(Text, nullable=True)
    test_ref = Column(Text, nullable=True)
    attributes = Column(Text, nullable=False, default="{}")
    owner_agent = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Judgment(Base):
    """One independent evaluation of a question against explicit evidence."""

    __tablename__ = "judgments"

    id = Column(Integer, primary_key=True, index=True)
    judge_name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    conclusion = Column(Text, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    conclusion_label = Column(String, nullable=True)
    evidence_ids = Column(Text, nullable=False, default="")
    uncertainty = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="completed")
    error = Column(Text, nullable=True)
    judgment_key = Column(String, nullable=False, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    research_task_id = Column(Integer, ForeignKey("research_tasks.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    claim = relationship("Claim", back_populates="judgments")
    evidence_links = relationship("EvidenceRelationship", back_populates="judgment", cascade="all, delete-orphan")


class JudgmentComparison(Base):
    """Durable comparison; disagreement is preserved, never averaged away."""

    __tablename__ = "judgment_comparisons"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    judgment_ids = Column(JSON, nullable=False)
    evidence_ids = Column(Text, nullable=False, default="")
    outcome = Column(String, nullable=False)  # agreement | partial_agreement | disagreement | missing_evidence
    summary = Column(Text, nullable=False)
    disagreement_points = Column(JSON, nullable=True)
    missing_evidence = Column(JSON, nullable=True)
    contradictory_claims = Column(JSON, nullable=True)
    unsupported_conclusions = Column(JSON, nullable=True)
    follow_up_question_id = Column(Integer, ForeignKey("research_questions.id"), nullable=True)
    comparison_key = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Prediction(Base):
    """A testable claim generated from a confident Belief. Resolved
    later by comparing the belief's confidence drift since the
    prediction was made — see reality_memory.resolve_pending_predictions()."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=False)
    statement = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")  # "pending" | "confirmed" | "failed"
    confidence_before = Column(Float, nullable=False)
    confidence_after = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------
# Forge Memory Layer
#
# Knowledge is Forge's permanent, retrievable memory — distinct from
# raw Signals (transient observations) and separate from Belief/Pattern
# (which already exist for reasoning). A Knowledge row is a synced,
# embedded copy of a Belief's or Pattern's current statement, kept up
# to date by belief_engine.py / pattern_engine.py whenever the source
# changes. This is what memory_layer.py searches over, and what gets
# retrieved as context before an AI provider (including a local Ollama
# model) answers a question — see ai_engine.answer_question().
# ---------------------------------------------------------------------


class Knowledge(Base):
    """A permanent, embedded, retrievable piece of Forge's knowledge —
    synced from a Belief or Pattern, never created standalone, so every
    entry always traces back to something Forge actually reasoned about
    (source_type + source_id) rather than floating free."""

    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=True)
    source_type = Column(String, nullable=False, index=True)  # "belief" | "pattern"
    source_id = Column(Integer, nullable=False, index=True)  # id within that source table
    confidence_score = Column(Float, nullable=False, default=50.0)  # mirrors the source's current confidence
    embedding = Column(Text, nullable=True)  # JSON-encoded list[float]
    embedding_model = Column(String, nullable=True)  # e.g. "hash-128" or "ollama:nomic-embed-text" — see embedding_engine.py
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Goal Engine
#
# The smallest viable next rung above Curiosity Engine / Research
# Planner on Forge's long-term architecture: something for Strategy
# Engine and Decision Engine (not yet built) to eventually optimize
# against, and something Curiosity Engine can already use today to
# prioritize questions by relevance instead of uniformly. Deliberately
# minimal — a Goal is a target, not a plan; reasoning about HOW to
# reach a goal is Strategy/Decision Engine's future job, not this
# table's.
# ---------------------------------------------------------------------


class Goal(Base):
    """Something Forge is currently trying to make progress toward.
    Opportunities can optionally link to the Goal they serve
    (Opportunity.goal_id); Curiosity Engine boosts a research
    question's priority when it overlaps an active goal's keywords."""

    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    statement = Column(Text, nullable=False)
    target_metric = Column(Text, nullable=True)  # optional measurable target, e.g. "$1,000 MRR" or "10 paying customers"
    status = Column(String, nullable=False, default="active")  # "active" | "paused" | "achieved" | "abandoned"
    priority = Column(Float, nullable=False, default=50.0)  # 0-100
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Confidence history
#
# Append-only log of every confidence change applied to a Belief,
# recorded at the single choke point all such changes flow through
# (BeliefEngine.adjust_confidence, plus the one inline merge-path nudge
# in form_or_update_belief). Never updated or overwritten once written
# — this is what lets Forge answer "how has my confidence in X
# evolved" instead of only ever knowing the current number. Not full
# belief versioning (the belief's other fields — statement, pattern_id
# — aren't tracked here); just the one thing that changes continuously
# and was previously lost every time it changed.
# ---------------------------------------------------------------------


class ConfidenceEvent(Base):
    """One recorded confidence change for a Belief."""

    __tablename__ = "confidence_events"

    id = Column(Integer, primary_key=True, index=True)
    belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=True)  # nullable as of v1.9 — see scenario_prediction_id below; a row always has exactly one of the two set, never both
    previous_confidence = Column(Float, nullable=False)
    new_confidence = Column(Float, nullable=False)
    delta = Column(Float, nullable=False)
    reason = Column(String, nullable=True)  # "reality_check" | "experiment" | "pattern_reoccurrence"
    evidence_signal_ids = Column(Text, nullable=True)  # comma-separated Signal ids involved in this specific change
    experiment_id = Column(Integer, ForeignKey("belief_experiments.id"), nullable=True)  # set only when reason == "experiment"
    created_at = Column(DateTime, default=utcnow)
    scenario_prediction_id = Column(Integer, ForeignKey("scenario_predictions.id"), nullable=True)  # v1.9 — a probability/confidence change for a ScenarioPrediction instead of a Belief. Same SQLite pre-existing-database caveat as Evidence.belief_id above.


# ---------------------------------------------------------------------
# Causal Knowledge Engine
#
# Turns "an experiment happened" (a free-text hypothesis/method/result
# triple in BeliefExperiment) into "this action under this condition
# produced this outcome" — a structured, reusable fact. Built
# automatically as a side effect of experiment_runner.record_result();
# see causal_engine.py.
# ---------------------------------------------------------------------


class CausalKnowledge(Base):
    """A structured causal fact: an action, tested under a condition,
    with an expected vs. actual outcome and a confidence that moves as
    more experiments test the SAME (condition, action) pair — repeated
    successes raise it, failures lower it (asymmetrically — see
    causal_engine.py). Matched and updated in place per unique
    (condition, action) pair, never duplicated."""

    __tablename__ = "causal_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    condition = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    expected_outcome = Column(Text, nullable=True)
    actual_outcome = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=50.0)  # 0-100
    belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)  # derived via belief -> pattern -> opportunity -> goal, if any
    supporting_experiment_ids = Column(Text, nullable=True)  # comma-separated BeliefExperiment ids
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Strategy Engine (v1.0)
#
# Forge's first attempt to answer "given everything I've learned, what
# should I try next toward this goal?" — WITHOUT executing anything.
# See strategy_engine.py's module docstring for the full design,
# including why Strategy rows are immutable once scored rather than
# updated in place.
# ---------------------------------------------------------------------


class Strategy(Base):
    """A candidate approach for making progress toward a Goal,
    generated by strategy_engine.py from Forge's own beliefs, causal
    knowledge, and evidence — never invented from generic model
    knowledge, and never executed. Immutable once created: a re-run
    that changes the picture creates a NEW row and marks the old one
    "superseded" rather than overwriting it."""

    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    expected_outcome = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=50.0)  # 0-100, the transparent composite score — see strategy_engine.py
    estimated_impact = Column(Float, nullable=False, default=50.0)  # 0-100
    uncertainty = Column(Float, nullable=False, default=50.0)  # 0-100, higher = less evidence backing this
    status = Column(String, nullable=False, default="candidate")  # "candidate" | "superseded"
    supporting_belief_ids = Column(Text, nullable=True)  # comma-separated Belief ids
    supporting_causal_knowledge_ids = Column(Text, nullable=True)  # comma-separated CausalKnowledge ids
    supporting_experiment_ids = Column(Text, nullable=True)  # comma-separated BeliefExperiment ids
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    goal = relationship("Goal")


# ---------------------------------------------------------------------
# Revenue Sources
#
# A named payout channel. Startup does not fill its percentages.
# A figure belongs here only when a primary terms page is stored.
# Opportunities can optionally link to one via
# Opportunity.revenue_source_id, grounding their monetization model in
# a real, verifiable mechanism instead of an assumed percentage.
# Linking is always explicit (an owner/API call), never auto-inferred —
# money_engine.suggest_revenue_sources() only proposes candidates.
# ---------------------------------------------------------------------


class RevenueSource(Base):
    """A real-world revenue-sharing mechanism with a documented payout
    structure. payout_share_percent_min/max is what YOU keep, not what
    the platform keeps. data_as_of matters — these terms change, and a
    stale figure presented as current would itself be a kind of
    fabrication; see money_engine.py's module docstring."""

    __tablename__ = "revenue_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)  # e.g. "Amazon Associates"
    source_type = Column(String, nullable=False)  # "affiliate" | "ad_revenue_share" | "marketplace" | "gig_platform" | "api_reseller" | "licensing" | "other"
    payout_structure = Column(Text, nullable=False)  # human-readable description of the actual terms
    payout_share_percent_min = Column(Float, nullable=True)  # what YOU keep, low end of the range
    payout_share_percent_max = Column(Float, nullable=True)  # what YOU keep, high end of the range
    minimum_payout = Column(Float, nullable=True)
    payment_frequency = Column(String, nullable=True)
    requires_approval = Column(Boolean, nullable=False, default=False)
    source_citation = Column(Text, nullable=True)  # where this figure came from
    data_as_of = Column(String, nullable=True)  # e.g. "2026-08" — these terms change; staleness must stay visible
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Autonomy Policy (v1.7)
#
# Represents the owner's operating authority — a boundary Forge can act
# freely INSIDE of, rather than requiring approval for every action.
# See autonomy_engine.py for how an action is evaluated against this.
# One active policy at a time (the current operating boundary); prior
# policies aren't deleted when replaced, just deactivated, preserving
# a history of how the boundary changed over time.
# ---------------------------------------------------------------------


class AutonomyPolicy(Base):
    """The owner-configured operating boundary. A conservative default
    is seeded on first run (see autonomy_engine.seed_default_policy()):
    zero autonomous spend, one concurrent experiment, a handful of
    daily actions, and only the free/low-risk action types allowed
    without approval — "do not create unlimited real-world authority
    without safeguards" is enforced by what this seeds to, not just
    stated."""

    __tablename__ = "autonomy_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, default="default")
    active = Column(Boolean, nullable=False, default=True)
    max_experiment_spend = Column(Float, nullable=True)  # None = no autonomous spending permitted at all; 0.0 = free actions only
    max_concurrent_experiments = Column(Integer, nullable=False, default=1)
    max_daily_actions = Column(Integer, nullable=False, default=3)
    max_retries = Column(Integer, nullable=False, default=1)  # per (opportunity, action_type) pair
    min_confidence_required = Column(Float, nullable=False, default=50.0)  # opportunity money_score floor for autonomous ALLOW
    max_risk_threshold = Column(Float, nullable=False, default=40.0)  # risk_score ceiling for autonomous ALLOW
    allowed_action_types = Column(Text, nullable=True)  # comma-separated subset of ACTION_TYPES; None = none allowed autonomously (safest default)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Scenario Engine (v1.9) — 2036 Civilization / Abundance Scenario Tracking
#
# A SECONDARY, parallel domain to ForgeOS's primary Revenue Intelligence
# mission. Nothing in this section is read or written by
# opportunity_engine.py, money_engine.py, execution_engine.py,
# autonomy_engine.py, or economic_intelligence.py — see scenario_engine.py's
# module docstring for the full reasoning and how Evidence/ConfidenceEvent
# are reused rather than duplicated.
# ---------------------------------------------------------------------


class Forecaster(Base):
    """An entity whose predictions Forge tracks and scores for accuracy
    over time. Storing a Forecaster's claim is NOT storing it as true —
    see ScenarioPrediction.status, which starts "open" and only moves
    to "confirmed"/"failed" once real evidence resolves it, exactly
    mirroring reality_memory.py's Prediction lifecycle for Beliefs."""

    __tablename__ = "forecasters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    track_record_accuracy = Column(Float, nullable=True)  # None = insufficient evidence; only ever computed from this forecaster's own resolved predictions, never asserted
    created_at = Column(DateTime, default=utcnow)


class Scenario(Base):
    """One of several mutually exclusive high-level futures Forge
    tracks evidence for. probability starts NULL ("insufficient
    evidence") for every scenario at seed time — not even an equal
    split — because a computed-looking number would misrepresent how
    little is actually known yet. See scenario_engine.DEFAULT_SCENARIOS."""

    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, nullable=False, unique=True)  # "A".."F"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    probability = Column(Float, nullable=True)  # 0-100; NULL = insufficient evidence
    probability_basis = Column(String, nullable=False, default="insufficient_evidence")  # "insufficient_evidence" | "evidence_derived"
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class ScenarioPrediction(Base):
    """A single testable claim — either attributed to a real Forecaster
    (forecaster_id set, with source_url/source_name/source_date
    required in practice) or generated by Forge itself as a tracked
    indicator (forecaster_id NULL). probability and confidence are
    DELIBERATELY separate columns, both NULL by default:

      probability = Forge's own estimated likelihood the predicted
                     event occurs — NOT the forecaster's stated
                     confidence, which is a different thing and often
                     isn't even given
      confidence  = Forge's confidence that the AVAILABLE EVIDENCE
                     actually supports the forecast — can be low even
                     for a probability Forge otherwise leans toward,
                     if the evidence behind it is thin

    original_quote (verbatim, when available) is kept separate from
    claim (which may be Forge's paraphrase) and from interpretation_note
    (an explicit note when Forge's classification goes beyond what was
    literally said) — never collapsed into one field that could blur
    what was actually said vs. what Forge inferred from it."""

    __tablename__ = "scenario_predictions"

    id = Column(Integer, primary_key=True, index=True)
    forecaster_id = Column(Integer, ForeignKey("forecasters.id"), nullable=True)  # NULL = a Forge-tracked indicator, not attributed to a person
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)  # linked only when the claim clearly matches one Scenario's definition — never forced
    domain = Column(String, nullable=True)  # e.g. "robotics" | "compute" | "labor" | free text; NULL if unclassified
    claim = Column(Text, nullable=False)
    original_quote = Column(Text, nullable=True)
    interpretation_note = Column(Text, nullable=True)
    target_date = Column(String, nullable=True)  # free text — real predictions are often fuzzy ranges, not a single date
    probability = Column(Float, nullable=True)  # 0-100; NULL = insufficient evidence
    confidence = Column(Float, nullable=True)  # 0-100; NULL = insufficient evidence
    reasoning = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    source_name = Column(Text, nullable=True)
    source_date = Column(String, nullable=True)
    status = Column(String, nullable=False, default="open")  # "open" | "confirmed" | "failed" | "ambiguous"
    outcome = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Source / World Intelligence — claims & ideas from external content
# Ingest is for text Forge is legitimately given access to (pasted
# transcript, licensed feed, user-provided article). Not a mass scraper.
# Claim ≠ truth. Verification and experiments come later.
# ---------------------------------------------------------------------


class WorldSourceDocument(Base):
    """A document/transcript Forge is allowed to process."""

    __tablename__ = "world_source_documents"

    id = Column(Integer, primary_key=True, index=True)
    source_uri = Column(String, nullable=True)  # URL or local label if known
    source_type = Column(String, nullable=False, default="text")
    # text | transcript | article | paper | user_note
    language_original = Column(String, nullable=True)
    language_internal = Column(String, nullable=False, default="en")
    title = Column(String, nullable=True)
    content_text = Column(Text, nullable=False)
    content_hash = Column(String, nullable=True, index=True)
    access_basis = Column(String, nullable=True)
    # user_provided | public_page | licensed | unknown
    retrieved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class MediaAnalysis(Base):
    """Durable media acquisition and extraction state."""

    __tablename__ = "media_analyses"

    id = Column(Integer, primary_key=True, index=True)
    source_uri = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False, default="youtube")
    external_id = Column(String, nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("world_source_documents.id"), nullable=True)
    status = Column(String, nullable=False, default="queued")
    title = Column(Text, nullable=True)
    channel = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    language = Column(String, nullable=True)
    transcript_source = Column(String, nullable=True)
    transcript_text = Column(Text, nullable=True)
    transcript_segments = Column(JSON, nullable=True)
    extraction_method = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    content_hash = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)


class WorldClaim(Base):
    """Extracted claim — not verified truth."""

    __tablename__ = "world_claims"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("world_source_documents.id"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String, nullable=True)
    # market_rule | pricing | demand | performance | factual | opinion | other
    domain = Column(String, nullable=True)  # trading | business | technology | other
    confidence_extract = Column(Float, nullable=True)  # extraction confidence only, not truth
    verification_status = Column(String, nullable=False, default="UNVERIFIED", index=True)
    # UNVERIFIED | INVESTIGATING | SUPPORTED | REFUTED | INCONCLUSIVE | REJECTED
    structured_json = Column(Text, nullable=True)  # machine-readable extract if any
    provenance_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class WorldIdea(Base):
    """Actionable idea derived from claims — still not an order or product."""

    __tablename__ = "world_ideas"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("world_source_documents.id"), nullable=True)
    claim_ids = Column(Text, nullable=True)  # comma-separated
    idea_text = Column(Text, nullable=False)
    domain = Column(String, nullable=True)
    status = Column(String, nullable=False, default="EXTRACTED")
    # EXTRACTED | QUEUED_FOR_TEST | TESTING | REJECTED | PROMISING | ARCHIVED
    linked_strategy_id = Column(String, nullable=True)  # if promoted to trading hypothesis
    linked_research_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Decision + Options + Learning (restored domain layer)
# ---------------------------------------------------------------------

class Option(Base):
    """A candidate path considered for an opportunity decision."""

    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    option_class = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    origin = Column(String, nullable=False, default="existing_evidence")
    evidence_ids = Column(Text, nullable=True)
    assumptions = Column(JSON, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    feasibility = Column(Float, nullable=True)
    risk = Column(Float, nullable=True)
    expected_benefit = Column(Float, nullable=True)
    timing = Column(Text, nullable=True)
    dependencies = Column(JSON, nullable=True)
    uncertainties = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="candidate")
    rejection_reason = Column(Text, nullable=True)
    identity_key = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

class Decision(Base):
    """A recorded choice among possible actions, with explicit rationale.

    Decisions are the link between understanding (beliefs/opportunities)
    and action. They capture WHY something was selected, not just what.
    """

    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=True)
    chosen_option_id = Column(Integer, ForeignKey("options.id"), nullable=True)
    option_space_status = Column(String, nullable=True)
    constraints = Column(JSON, nullable=True)

    title = Column(String, nullable=False)
    rationale = Column(Text, nullable=False)  # WHY this was chosen
    alternatives_considered = Column(Text, nullable=True)  # what was rejected and why
    expected_outcome = Column(Text, nullable=True)
    expected_cost = Column(Float, nullable=True)  # ESTIMATE
    expected_value = Column(Float, nullable=True)  # ESTIMATE
    risk_notes = Column(Text, nullable=True)
    confidence_at_decision = Column(Float, nullable=True)  # 0-100 snapshot
    status = Column(String, nullable=False, default="proposed")  # proposed | accepted | rejected | superseded
    created_at = Column(DateTime, default=utcnow)
    decided_at = Column(DateTime, nullable=True)


class LearningEvent(Base):
    """Record of expected-vs-actual comparison that can update beliefs.

    This is the measurement → learning link. Not free-text only:
    structured prediction error so future decisions can weight it.
    """

    __tablename__ = "learning_events"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True)
    belief_experiment_id = Column(Integer, ForeignKey("belief_experiments.id"), nullable=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=True)

    prediction = Column(Text, nullable=False)  # what was expected
    actual = Column(Text, nullable=False)  # what happened
    prediction_error = Column(Float, nullable=True)  # structured error if numeric (-1..1 or absolute)
    error_type = Column(String, nullable=True)  # overestimate | underestimate | qualitative_miss | confirmed
    lesson = Column(Text, nullable=False)
    belief_update_applied = Column(Boolean, nullable=False, default=False)
    confidence_delta = Column(Float, nullable=True)  # applied change, if any
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    data_scope = Column(String, nullable=False, default="REAL", index=True)  # inherited from the outcome that produced this learning
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------
# Lessons Memory (v2.10) — durable, consolidated learning
# Forge's long-term "what it has actually learned", distilled from real
# LearningEvents (which themselves come only from real ACTUAL outcomes).
# The consolidate recall loop mirrors how the operator's own assistant
# files facts into memory pages and recalls them into later reasoning:
#   - consolidate(): merge a new LearningEvent into a themed Lesson
#                    (dedupe by theme key, bump hit_count/last_seen).
#   - recall():      surface relevant Lessons when reasoning about an
#                    opportunity/decision, so past reality informs what
#                    ForgeOS pursues next.
# No Lesson is ever fabricated: they exist only if a real LearningEvent
# produced them.
# ---------------------------------------------------------------------

class Lesson(Base):
    """A consolidated, durable lesson distilled from real LearningEvents."""

    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    theme_key = Column(String, nullable=False, index=True)  # normalized theme (dedupe key)
    title = Column(String, nullable=False)  # human-readable headline of the lesson
    summary = Column(Text, nullable=False)  # consolidated lesson text

    # What the lesson is about (nullable links; a lesson can be general)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    belief_id = Column(Integer, ForeignKey("beliefs.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

    # aggregated evidence + provenance (from the events that fed it)
    error_type = Column(String, nullable=True)  # overestimate | underestimate | qualitative_miss | confirmed
    prediction_error_avg = Column(Float, nullable=False, default=0.0)
    hit_count = Column(Integer, nullable=False, default=0)  # how many LearningEvents consolidated here
    source_learning_event_ids = Column(Text, nullable=True)  # comma-separated ids, for provenance

    first_seen = Column(DateTime, default=utcnow)
    last_seen = Column(DateTime, default=utcnow)

    # lifecycle
    active = Column(Boolean, nullable=False, default=True)  # false once superseded/contradicted
    superseded_by_id = Column(Integer, nullable=True)
    data_scope = Column(String, nullable=False, default="REAL", index=True)  # REAL lessons affect real metrics; SANDBOX lessons stay visibly test-only
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class Action(Base):
    """A concrete unit of work proposed from a Decision.

    Execution success != outcome success. Status VERIFIED only after
    reality is checked, not merely because code returned OK.
    """

    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)

    action_type = Column(String, nullable=False, index=True)
    # manual_note | research | outreach | interview | http_request | unsupported
    objective = Column(Text, nullable=False)
    parameters_json = Column(Text, nullable=True)  # structured inputs, not free invention
    status = Column(String, nullable=False, default="PROPOSED", index=True)
    # PROPOSED | APPROVAL_REQUIRED | APPROVED | RUNNING | SUCCEEDED | FAILED | CANCELLED | VERIFIED
    policy_result = Column(String, nullable=True)  # ALLOW | REQUIRE_APPROVAL | BLOCK
    policy_reason = Column(Text, nullable=True)

    proposed_at = Column(DateTime, default=utcnow)
    approved_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    execution_result = Column(Text, nullable=True)  # what the adapter returned (e.g. "message queued")
    execution_error = Column(Text, nullable=True)
    verification_state = Column(String, nullable=False, default="UNVERIFIED")
    # UNVERIFIED | VERIFIED_SUCCESS | VERIFIED_FAILURE | UNSUPPORTED
    external_ref = Column(String, nullable=True)
    adapter_name = Column(String, nullable=True)


class Outcome(Base):
    """Observed reality after an action/experiment — never a prediction.

    Predicted values must NOT be written here. Only ACTUAL measured facts.
    """

    __tablename__ = "outcomes"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)  # rollup target

    observed_at = Column(DateTime, default=utcnow, index=True)
    outcome_type = Column(String, nullable=False, index=True)
    # ACTUAL_REVENUE | ACTUAL_COST | ACTUAL_RESPONSE | ACTUAL_CUSTOMERS | ACTUAL_CONVERSION | QUALITATIVE | OTHER
    actual_value = Column(Float, nullable=True)  # ACTUAL only — never estimated
    unit = Column(String, nullable=True)  # NPR, count, percent, ...
    qualitative_result = Column(Text, nullable=True)
    source = Column(String, nullable=False, default="manual")  # provenance of the measurement
    success = Column(Boolean, nullable=True)  # relative to the action's objective, if known
    verification_state = Column(String, nullable=False, default="REPORTED")
    # REPORTED | VERIFIED | DISPUTED
    notes = Column(Text, nullable=True)
    data_scope = Column(String, nullable=False, default="REAL", index=True)  # REAL | SANDBOX; only REAL outcomes roll into business metrics


class Provider(Base):
    """Publicly visible service provider record.

    This is the public-facing identity model for a real provider/service
    network. It is intentionally distinct from ForgeOS Product, which remains
    an internal offer/business lifecycle record.
    """

    __tablename__ = "public_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    business_name = Column(String, nullable=True)
    category = Column(String, nullable=True, index=True)
    summary = Column(Text, nullable=True)
    region = Column(String, nullable=True, index=True)
    city = Column(String, nullable=True, index=True)
    country = Column(String, nullable=False, default="Nepal")
    website = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    public_visible = Column(Boolean, nullable=False, default=False, index=True)
    verification_status = Column(String, nullable=False, default="unverified", index=True)
    verification_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    listings = relationship("ServiceListing", back_populates="provider", cascade="all, delete-orphan")
    verification_records = relationship("VerificationRecord", back_populates="provider", cascade="all, delete-orphan")
    booking_requests = relationship("BookingRequest", back_populates="provider", cascade="all, delete-orphan")


class ServiceListing(Base):
    """A concrete public service listing under a verified provider."""

    __tablename__ = "public_service_listings"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("public_providers.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, nullable=True, index=True)
    location = Column(String, nullable=True)
    price_from = Column(String, nullable=True)
    currency = Column(String, nullable=False, default="NPR")
    availability_status = Column(String, nullable=False, default="pending", index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    public_visible = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    provider = relationship("Provider", back_populates="listings")
    booking_requests = relationship("BookingRequest", back_populates="service_listing", cascade="all, delete-orphan")


class VerificationRecord(Base):
    """Public verification history for a provider."""

    __tablename__ = "public_verification_records"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("public_providers.id"), nullable=False, index=True)
    verification_status = Column(String, nullable=False, default="pending", index=True)
    evidence_type = Column(String, nullable=True)
    evidence_reference = Column(String, nullable=True)
    reviewed_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    provider = relationship("Provider", back_populates="verification_records")


class BookingRequest(Base):
    """Customer request against a public service listing."""

    __tablename__ = "public_booking_requests"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("public_providers.id"), nullable=False, index=True)
    service_listing_id = Column(Integer, ForeignKey("public_service_listings.id"), nullable=True, index=True)
    requester_name = Column(String, nullable=False)
    requester_phone = Column(String, nullable=True)
    requester_email = Column(String, nullable=True)
    requested_service = Column(String, nullable=False)
    requested_date = Column(String, nullable=True)
    requested_time = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending", index=True)
    provider_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    accepted_at = Column(DateTime, nullable=True)

    provider = relationship("Provider", back_populates="booking_requests")
    service_listing = relationship("ServiceListing", back_populates="booking_requests")


class Product(Base):
    """A concrete offer derived from an Opportunity.

    The Product is the *formal handoff* from discovery to build/distribute:
    an Opportunity names a problem + customer + solution, and a Product
    names the specific offer and its launch state. It is always honest:
    a Product is a HYPOTHESIS to validate, never a claim of shipped value.
    Revenue/customers recorded against a Product come ONLY from linked
    real Outcomes (ACTUAL_* values), never fabricated here.
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True, index=True)

    name = Column(String, nullable=False)  # concrete offer name (artifact of the opportunity's solution)
    offer = Column(Text, nullable=False)  # what is actually being sold/delivered, in plain words
    target_customer = Column(Text, nullable=True)
    pricing = Column(Text, nullable=True)  # how customers pay / price idea — never a claimed figure
    mvp_scope = Column(Text, nullable=True)  # what the first version actually consists of

    status = Column(String, nullable=False, default="concept", index=True)
    # concept -> validating -> launched -> iterating -> retired
    launch_state = Column(String, nullable=True)  # "not_launched" | "piloting" | "public" — real state only
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)
    retired_at = Column(DateTime, nullable=True)
    retirement_reason = Column(Text, nullable=True)

    # --- Evidence-gated numbers (never fabricated) ---
    # updated ONLY from real linked Outcome rows (ACTUAL_REVENUE / ACTUAL_CUSTOMERS).
    actual_customers = Column(Integer, nullable=False, default=0)  # from ACTUAL_CUSTOMERS outcomes
    actual_revenue = Column(Float, nullable=False, default=0.0)  # from ACTUAL_REVENUE outcomes, sum
    actual_cost = Column(Float, nullable=False, default=0.0)  # from ACTUAL_COST outcomes, sum

    # meta
    hypothesis = Column(Text, nullable=True)  # what we believe must be true for this to be worth building
    data_scope = Column(String, nullable=False, default="REAL", index=True)  # sandbox products are never reported as real traction
    # Structured offer-preparation artifact. These fields describe a hypothesis
    # and owner review state; they never imply a customer, sale, or payment.
    offer_brief_json = Column(Text, nullable=True)
    approval_status = Column(String, nullable=False, default="PENDING_REVIEW", index=True)
    approval_note = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    opportunity = relationship("Opportunity")
    channels = relationship("DistributionChannel", back_populates="product", cascade="all, delete-orphan")
    customer_events = relationship("CustomerEvent", back_populates="product", cascade="all, delete-orphan")

    @property
    def offer_brief(self):
        if not self.offer_brief_json:
            return None
        try:
            value = json.loads(self.offer_brief_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None


class DistributionChannel(Base):
    """A channel through which a Product is distributed / promoted.

    Records the *leaf* of a campaign: one outreach action on one channel.
    Ties to a real Action/Outcome for provenance. Never invents reach or
    conversion — those numbers only appear from real Outcome records.
    (Checklist #17: distribution/campaign/customer tracking, honest.)
    """

    __tablename__ = "distribution_channels"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)

    channel_type = Column(String, nullable=False)
    # "manual_outreach" | "paid_ads" | "content" | "marketplace" | "partnership" | "direct_sales" | "other"
    name = Column(String, nullable=False)  # e.g. "Fiverr gig", "Reddit r/repairshops", "local Facebook group"
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="planned")
    # planned -> active -> paused -> retired

    # provenance: which action this distribution effort corresponds to
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    # --- honest metrics ---
    outreach_count = Column(Integer, nullable=False, default=0)  # real counted, from outcomes
    response_count = Column(Integer, nullable=False, default=0)
    conversion_count = Column(Integer, nullable=False, default=0)
    data_scope = Column(String, nullable=False, default="REAL", index=True)

    product = relationship("Product", back_populates="channels")
    customer_events = relationship("CustomerEvent", back_populates="channel")


class CustomerEvent(Base):
    """A ledger entry for a real prospect/customer contact.

    This is the ground truth of who was actually reached, when, and what
    happened. An entry records provenance (source action/outcome). Do NOT
    write speculative/fake prospects here — only real contacts.
    (Checklist #17: customer/lead tracking, honest.)
    """

    __tablename__ = "customer_events"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    channel_id = Column(Integer, ForeignKey("distribution_channels.id"), nullable=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)

    contact_name = Column(String, nullable=True)  # optional; privacy-respecting
    contact_identifier = Column(String, nullable=True)  # handle/email-like, stored only as given
    segment = Column(String, nullable=True)  # human-readable segment (e.g. "independent repair shop")

    stage = Column(String, nullable=False, default="lead")
    # lead -> contacted -> interested -> paid_customer -> churned
    event_type = Column(String, nullable=True)  # "outbound", "inbound", "response", "signup", "purchase"
    notes = Column(Text, nullable=True)

    # provenance — never fabricated
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=True)
    outcome_id = Column(Integer, ForeignKey("outcomes.id"), nullable=True)

    occurred_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)
    data_scope = Column(String, nullable=False, default="REAL", index=True)  # SANDBOX contacts are excluded from real customer counts

    product = relationship("Product", back_populates="customer_events")
    channel = relationship("DistributionChannel", back_populates="customer_events")


class Customer(Base):
    """Privacy-minimized repair-shop customer record."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact_identifier = Column(String, nullable=True)
    consent_state = Column(String, nullable=False, default="NOT_REQUIRED")
    data_scope = Column(String, nullable=False, default="SANDBOX", index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    work_items = relationship("RepairWorkItem", back_populates="customer")


class RepairWorkItem(Base):
    """The smallest auditable repair-shop unit, linked to existing Forge objects."""

    __tablename__ = "repair_work_items"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    asset_label = Column(String, nullable=False)
    reported_problem = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="INTAKE", index=True)
    data_scope = Column(String, nullable=False, default="SANDBOX", index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True, index=True)
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    customer = relationship("Customer", back_populates="work_items")
    events = relationship("WorkItemEvent", back_populates="work_item", cascade="all, delete-orphan")
    communications = relationship("CustomerCommunication", back_populates="work_item", cascade="all, delete-orphan")


class WorkItemEvent(Base):
    """Append-only transition and audit record for a repair work item."""

    __tablename__ = "work_item_events"

    id = Column(Integer, primary_key=True, index=True)
    work_item_id = Column(Integer, ForeignKey("repair_work_items.id"), nullable=False, index=True)
    actor = Column(String, nullable=False, default="operator")
    event_type = Column(String, nullable=False)
    previous_state = Column(String, nullable=True)
    next_state = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    evidence_ids = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    work_item = relationship("RepairWorkItem", back_populates="events")


class CustomerCommunication(Base):
    """Reviewed customer status/estimate; sending is never implicit."""

    __tablename__ = "customer_communications"

    id = Column(Integer, primary_key=True, index=True)
    work_item_id = Column(Integer, ForeignKey("repair_work_items.id"), nullable=False, index=True)
    channel = Column(String, nullable=False, default="manual")
    body = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="DRAFT", index=True)
    customer_response = Column(Text, nullable=True)
    action_id = Column(Integer, ForeignKey("actions.id"), nullable=True)
    integration_delivery_id = Column(Integer, ForeignKey("integration_deliveries.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    work_item = relationship("RepairWorkItem", back_populates="communications")


class IntegrationDelivery(Base):
    """Durable local outbox record for optional external integrations.

    ForgeOS remains usable when an external service is unavailable. A delivery
    is persisted before attempting network I/O, and idempotency prevents a retry
    from becoming a duplicate message/payment/CRM event.
    """
    __tablename__ = "integration_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    integration_name = Column(String, nullable=False, index=True)
    operation = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    request_json = Column(Text, nullable=False, default="{}")
    response_json = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="QUEUED", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class DomainRecord(Base):
    """A job, offer, or trade created inside ForgeOS. Not scraped from anywhere else."""

    __tablename__ = "domain_records"

    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=False, index=True)  # job | offer | trade
    title = Column(String, nullable=False)
    detail = Column(Text, nullable=False)
    city = Column(String, nullable=True, index=True)
    stated_price = Column(String, nullable=True)
    terms = Column(Text, nullable=True)  # JSON economic contract; work is not accepted without it
    status = Column(String, nullable=False, default="open", index=True)  # open | closed
    close_result = Column(String, nullable=True)  # completed | withdrawn | paid
    close_note = Column(Text, nullable=True)
    close_token_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    closed_at = Column(DateTime, nullable=True)


class NetworkConnection(Base):
    """A relation between canonical records with a separate match lifecycle."""

    __tablename__ = "network_connections"

    id = Column(Integer, primary_key=True, index=True)
    left_kind = Column(String, nullable=False)
    left_id = Column(Integer, nullable=False, index=True)
    right_kind = Column(String, nullable=False)
    right_id = Column(Integer, nullable=False, index=True)
    relation_type = Column(String, nullable=True, default="possible_match", index=True)
    direction = Column(String, nullable=False, default="directed")
    epistemic_state = Column(String, nullable=True, default="hypothesized", index=True)
    context = Column(JSON, nullable=True)
    uncertainty = Column(JSON, nullable=True)
    provenance = Column(JSON, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    # Retained for rows written by the superseded entity/relation graph.
    relation_id = Column(Integer, ForeignKey("relations.id"), nullable=True, index=True)
    state = Column(String, nullable=False, default="candidate", index=True)
    reason = Column(Text, nullable=False)
    evidence_reference = Column(Text, nullable=True)
    constraints = Column(Text, nullable=True)
    known = Column(Text, nullable=True)
    unknown = Column(Text, nullable=True)
    agreement_gap = Column(Text, nullable=False)
    observed_at = Column(DateTime, default=utcnow)
    public_visible = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class EarningOffer(Base):
    """A Nepal-first earning hypothesis owned by a local workspace token."""
    __tablename__ = "earning_offers"

    id = Column(Integer, primary_key=True, index=True)
    workspace_key_hash = Column(String, nullable=False, index=True)
    pathway = Column(String, nullable=False)
    title = Column(String, nullable=False)
    skill = Column(String, nullable=False)
    customer = Column(String, nullable=False)
    price_npr = Column(Integer, nullable=True)
    age_band = Column(String, nullable=False)  # 14_17 | 18_plus
    status = Column(String, nullable=False, default="draft", index=True)
    next_actions_json = Column(Text, nullable=False, default="[]")
    outcome_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class CycleRun(Base):
    """Observability record for one worker / forge_loop cycle."""

    __tablename__ = "cycle_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False, default=utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="RUNNING")  # RUNNING | COMPLETED | FAILED
    summary_json = Column(Text, nullable=True)  # stage counts + per-stage errors
    error = Column(Text, nullable=True)


# ---------------------------------------------------------------------
# Scout + Draft + Approval Queue (2026-10-05)
#
# Candidate registry for potential sellers/businesses. Built ON the six
# primitives: candidates are SubstrateEntity rows (entity_type=
# "scout_candidate"), observations are Evidence rows, sends are
# WorldEvent + Action rows. These three tables hold only the
# outreach-specific workflow state that the primitives don't cover.
#
# HARD RULE: nothing here sends a message. Drafts are prepared;
# the OWNER sends from their own account and marks SENT. No autonomous
# sending exists anywhere in this codebase.
# ---------------------------------------------------------------------


class OutreachDraft(Base):
    """A prepared first-contact message for one scout candidate.

    Status flow: DRAFT -> APPROVED -> SENT, or DRAFT -> SKIPPED.
    The owner edits the text, approves, sends from their own account,
    then marks SENT (logging the send as an Event/Action). Replies and
    outcomes are recorded here — never invented.
    """

    __tablename__ = "outreach_drafts"

    id = Column(Integer, primary_key=True, index=True)
    candidate_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    # The specific observed fact that prompted contact (e.g. "3 unanswered
    # inquiry comments on your Facebook page on 2026-10-01").
    observed_fact = Column(Text, nullable=False)
    message_en = Column(Text, nullable=False)
    message_ne = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="DRAFT", index=True)
    # DRAFT | APPROVED | SKIPPED | SENT
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)  # "owner"
    sent_at = Column(DateTime, nullable=True)
    sent_by = Column(String, nullable=True)  # owner account identifier
    send_channel = Column(String, nullable=True)  # e.g. "facebook", "viber", "whatsapp"
    reply_received = Column(Boolean, nullable=False, default=False)
    reply_at = Column(DateTime, nullable=True)
    reply_summary = Column(Text, nullable=True)
    outcome_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    candidate = relationship("SubstrateEntity", foreign_keys=[candidate_entity_id])


class DoNotContact(Base):
    """Businesses/people that must never be contacted. Checked before any
    draft is created or approved."""

    __tablename__ = "do_not_contact"

    id = Column(Integer, primary_key=True, index=True)
    candidate_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, unique=True, index=True)
    reason = Column(Text, nullable=False)
    added_at = Column(DateTime, default=utcnow)
    added_by = Column(String, nullable=False, default="owner")


class OutreachConfig(Base):
    """Singleton outreach workflow configuration."""

    __tablename__ = "outreach_config"

    id = Column(Integer, primary_key=True)
    daily_cap = Column(Integer, nullable=False, default=5)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
