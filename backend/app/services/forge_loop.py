"""
FORGE LOOP — the intelligence cycle orchestrator
===================================================

Ties every engine together into one runnable cycle:

    1. Observer Engine   -> pull the current pool of signals
    2. Pattern Engine     -> detect repeated problems across them
    3. Belief Engine        -> form/update beliefs from those patterns
    4. Reality Checker       -> re-score EXISTING beliefs against all
                                 current signals (confidence can rise
                                 or fall; evidence is persisted to
                                 Reality Memory)
    5. Reality Memory          -> resolve any pending Predictions whose
                                    belief has since been re-checked
                                    (confirmed/failed — this is where
                                    source reliability gets adjusted),
                                    then generate new Predictions for
                                    beliefs confident enough to test
    6. Curiosity Engine          -> find weak spots (low-confidence
                                      beliefs, unexplored patterns,
                                      contradictions) and turn them into
                                      research questions
    7. Research Planner            -> turn open questions into concrete,
                                        source-tagged research tasks
    8. Rare Signal Engine             -> persist explainable weak-signal
                                       assessments and route high-scoring
                                       ones into the research planner
    9. Opportunity Engine              -> review patterns with no Opportunity
                                          yet against real economic evidence
                                          and create opportunities that earn
                                          them (v1.8)
    9.1 Opportunity claim links        -> opportunity evidence -> source-linked
                                          claim -> research question
    9.5 Substrate adapters             -> refresh additive projections from
                                          source-of-truth tables (entities,
                                          relations, events, capabilities)
    10. Money Engine                   -> classify monetization models and
                                          flag opportunities needing
                                          revenue validation (v1.2).
                                          Identification only — never
                                          creates a revenue experiment,
                                          contacts anyone, or spends
                                          anything. See
                                          money_engine.run_money_cycle().
    11. Execution Engine               -> propose (never execute) low-risk
                                          actions against the owner's
                                          AutonomyPolicy
    11.5 Decision Engine               -> propose validation decisions for
                                          high-value unvalidated
                                          opportunities
    11.6 Lessons Engine               -> consolidate LearningEvents into
                                         durable Lessons and recall them for
                                         the top opportunity (v2.10)
    11.7 Orchestrator                 -> advance top unvalidated
                                         opportunities through accepted
                                         decision -> validation Experiment +
                                         human-executable task (v2.11)
    12. Scenario Engine               -> SECONDARY domain: scan signals for
                                         robotics/compute relevance against
                                         the 2036-scenario indicators.
                                         Non-blocking by construction — a
                                         failure here never 500s the cycle.
    13. Action proposal                -> propose actions from recent
                                          accepted decisions (policy-gated)
    14. Revenue miner                  -> review recorded paid offers; never
                                          contacts anyone or moves money

A fatal failure in stages 1-14 marks the whole CycleRun FAILED honestly
and re-raises; several stages capture their own errors independently
(opportunity_claim_questions, substrate_adapters, decision_proposal,
lessons_memory, orchestration, action_proposal, revenue_miner) so one
bad stage doesn't poison the rest of the run.

This is the single orchestrator for the whole loop — there is
deliberately no separate "reality_engine.py"; that would just be a
second module doing this same job. Triggered on-demand via
POST /forge/cycle, or automatically by the Background Forge Worker
(backend/worker.py), which is a separate process that calls this same
function on an interval — see worker.py for why that lives outside the
FastAPI process instead of a `while True` loop in here.

Patterns are synced into the Forge Memory Layer (Knowledge) here rather
than inside pattern_engine.py itself — doing it there would create a
circular import (pattern_engine -> memory_layer -> embedding_engine ->
pattern_engine, since embedding_engine reuses pattern_engine's
tokenizer). Keeping the sync call at the orchestration level avoids
that entirely.
"""

from sqlalchemy.orm import Session

from app.services import (
    pattern_engine,
    belief_engine,
    reality_checker,
    reality_memory,
    curiosity_engine,
    research_planner,
    memory_layer,
    money_engine,
    execution_engine,
    opportunity_engine,
    rare_signal_engine,
    scenario_engine,
)
from app.services.observer_engine import ObserverEngine
from typing import Optional


def run_cycle(db: Session, data_scope: str = "REAL") -> dict:
    """Mark the cycle FAILED honestly on fatal stage failure, then re-raise."""
    if data_scope not in {"REAL", "SANDBOX"}:
        raise ValueError("Invalid data_scope")
    try:
        return _run_cycle_impl(db, data_scope)
    except Exception as exc:
        db.rollback()
        from app import models
        from datetime import datetime, timezone
        row = db.query(models.CycleRun).filter_by(status="RUNNING").order_by(models.CycleRun.id.desc()).first()
        if row:
            row.status = "FAILED"
            row.ended_at = datetime.now(timezone.utc)
            row.error = str(exc)
            try:
                db.commit()
            except Exception:
                db.rollback()
        raise


def _run_cycle_impl(db: Session, data_scope: str = "REAL") -> dict:
    """Run one full Forge intelligence cycle and return a summary.

    Records a CycleRun for observability. Stage failures are captured
    independently — one failure must not paint the whole cycle successful.
    """
    import json
    import os
    from datetime import datetime, timezone
    from app import models as _models
    from app.services import (
        evidence_graph,
        capability_substrate_adapter,
        evidence_relationship_substrate_adapter,
        legacy_evidence_substrate_adapter,
        legacy_record_substrate_adapter,
        market_signal_substrate_adapter,
        research_question_relation_substrate_adapter,
        network_connections,
        network_substrate_adapter,
        public_services_substrate_adapter,
        research_task_event_substrate_adapter,
        world_graph,
    )

    cycle = _models.CycleRun(started_at=datetime.now(timezone.utc), status="RUNNING")
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    stage_errors: dict = {}

    # 1. Signals currently in memory
    observer = ObserverEngine(db)
    signals_processed = len(observer.list_signals(limit=1000, min_importance=0.0))

    # 1.5. Complete the canonical signal-to-network handoff here so API,
    # scheduled, and worker cycles share the same behavior. External
    # observations become explicitly observed claims only when a canonical
    # source URL and existing Evidence row are present. Candidate connections
    # stay private and unapproved until a person advances them.
    # Operator-set env limits must never fail the whole cycle on a typo:
    # garbage falls back to the default instead of a bare ValueError.
    try:
        claim_limit = max(0, min(int(os.environ.get("FORGEOS_CLAIM_LINK_LIMIT", "20")), 100))
    except (TypeError, ValueError):
        claim_limit = 20
    source_addresses_restored = evidence_graph.restore_source_addresses(db, limit=claim_limit)
    linked_claim_ids = evidence_graph.link_unclaimed_observations(db, limit=claim_limit)
    connection_rows = network_connections.scan_candidates(db, limit=50)
    network_connection_ids = [row.id for row in connection_rows]

    # 2. Detect patterns across all signals. Each Pattern already
    #    carries its own origin_signal_ids (exact, not approximated —
    #    see pattern_engine.py), so no separate lookup is needed here
    #    anymore. Sync each into the Memory Layer.
    patterns = pattern_engine.run_pattern_detection(db)
    for pattern in patterns:
        memory_layer.sync_pattern_to_knowledge(db, pattern)

    # 3. Form/update a belief for every detected pattern. Belief
    #    formation records initial Evidence and syncs to Knowledge
    #    itself — see belief_engine.py.
    be = belief_engine.BeliefEngine(db)
    beliefs_updated = 0
    for pattern in patterns:
        supporting_ids = _parse_signal_ids(pattern.origin_signal_ids)
        be.form_belief_from_pattern(pattern, supporting_signal_ids=supporting_ids)
        beliefs_updated += 1

    # 4. Reality-check every existing belief against current signals
    #    (not just the ones just formed — confidence should drift over
    #    time as new, unrelated signals accumulate too). Evidence is
    #    persisted to Reality Memory, and Knowledge re-synced, inside
    #    check_belief() / adjust_confidence().
    from app import models  # local import, matching this module's style

    existing_beliefs = be.list_beliefs(limit=200)
    all_signals = db.query(models.Signal).all()  # loaded once: check_belief must not re-scan per belief
    for belief in existing_beliefs:
        reality_checker.check_belief(db, belief, signals=all_signals)

    # 5a. Resolve any pending predictions whose belief was just re-checked.
    #     This is where source reliability actually moves.
    resolved_predictions = reality_memory.resolve_pending_predictions(db)

    # 5b. Generate new predictions for beliefs confident enough to test.
    predictions_before = {p.id for p in reality_memory.list_predictions(db, limit=1000)}
    for belief in be.list_beliefs(limit=200):
        reality_memory.generate_prediction(db, belief)
    predictions_after = {p.id for p in reality_memory.list_predictions(db, limit=1000)}
    predictions_created = len(predictions_after - predictions_before)

    # 6. Curiosity scan -> new research questions from weak spots
    ce = curiosity_engine.CuriosityEngine(db)
    new_questions = ce.run_curiosity_scan()

    # 7. Plan research tasks for open questions
    new_tasks = research_planner.plan_tasks_for_open_questions(db)

    # 8. Rare Signal Detection (v2.6): persist explainable weak-signal
    # assessments and route high-scoring ones into the existing P1
    # research planner. Detection is heuristic; no opportunity is made
    # here and no score is treated as truth.
    rare_assessments = rare_signal_engine.detect_rare_signals(db)
    rare_questions = rare_signal_engine.trigger_research_for_rare_signals(db, rare_assessments)

    # 9. Economic Intelligence (v1.8): review every Pattern with no
    #    Opportunity yet against real economic evidence — a problem, an
    #    identifiable customer, and at least one of pain/demand/
    #    monetary-impact/solution-gap, all backed by matched text, never
    #    guessed. This is THE fix for patterns accumulating with zero
    #    opportunities ever emerging: before v1.8, nothing autonomous
    #    ever called any opportunity-creation path at all. See
    #    opportunity_engine.run_autonomous_opportunity_discovery()'s
    #    docstring.
    discovery_summary = opportunity_engine.run_autonomous_opportunity_discovery(db)

    # 9.1. Complete only the stored public path from opportunity evidence to
    #      source-linked claim to research question. Publication eligibility
    #      and regulated-asset review are applied before the question link is
    #      created; the feed remains the final visibility gate.
    opportunity_questions_linked = 0
    try:
        opportunity_questions_linked = (
            opportunity_engine.link_opportunity_evidence_to_claim_questions(db)
        )
    except Exception as exc:
        stage_errors["opportunity_claim_questions"] = str(exc)
        try:
            db.rollback()
        except Exception:
            pass

    # 9.5. Refresh the additive substrate projections from their existing
    #      source-of-truth tables. These adapters only write typed references,
    #      relations, and provenance events; legacy payloads remain authoritative.
    substrate_summary = {
        "entities_created": 0,
        "relations_created": 0,
        "events_created": 0,
        "ambiguous_links": 0,
        "network_connections_projected": 0,
        "network_connections_unresolved": 0,
        "network_truth_waiting_for_evidence": 0,
        "public_services_projected": 0,
        "public_services_unresolved": 0,
        "substrate_evidence_created": 0,
        "capabilities_created": 0,
        "capabilities_refreshed": 0,
        "capability_events_created": 0,
        "legacy_records_projected": 0,
        "legacy_records_unresolved": 0,
        "legacy_evidence_mapped": 0,
        "legacy_evidence_unresolved": 0,
        "legacy_evidence_batch_seen": 0,
        "evidence_relationships_projected": 0,
        "evidence_relationships_unresolved": 0,
        "research_question_relations_projected": 0,
        "research_question_relations_unresolved": 0,
        "research_task_events_projected": 0,
        "research_task_events_unresolved": 0,
    }
    try:
        intelligence_projection = world_graph.sync_intelligence_path(db, limit=100)
        operational_projection = world_graph.sync_action_outcome_learning_path(db, limit=100)
        network_projection = network_substrate_adapter.sync_network_connections(db, limit=100)
        public_services_projection = public_services_substrate_adapter.sync_public_services(db, limit=100)
        tool_capability_projection = capability_substrate_adapter.sync_runtime_tool_capabilities(db)
        legacy_record_projection = legacy_record_substrate_adapter.sync_legacy_records(db, limit=250)
        legacy_evidence_projection = legacy_evidence_substrate_adapter.sync_legacy_evidence(
            db,
            limit=max(1, min(int(os.environ.get("FORGEOS_SUBSTRATE_EVIDENCE_BATCH", "500")), 2000)),
        )
        evidence_relationship_projection = evidence_relationship_substrate_adapter.sync_evidence_relationships(
            db,
            limit=max(1, min(int(os.environ.get("FORGEOS_SUBSTRATE_LINK_BATCH", "250")), 2000)),
        )
        research_question_relation_projection = (
            research_question_relation_substrate_adapter.sync_research_question_sources(db, limit=250)
        )
        research_task_event_projection = (
            research_task_event_substrate_adapter.sync_research_task_events(db, limit=250)
        )
        substrate_summary["entities_created"] = (
            intelligence_projection["entities_created"]
            + operational_projection["entities_created"]
        )
        substrate_summary["relations_created"] = (
            intelligence_projection["relations_created"]
            + operational_projection["relations_created"]
        )
        substrate_summary["events_created"] = operational_projection["events_created"]
        substrate_summary["events_created"] += network_projection["events_created"]
        substrate_summary["ambiguous_links"] = operational_projection["ambiguous_links"]
        substrate_summary["network_connections_projected"] = network_projection["projected_connections"]
        substrate_summary["network_connections_unresolved"] = network_projection["unresolved_connections"]
        substrate_summary["network_truth_waiting_for_evidence"] = network_projection[
            "epistemic_state_pending_evidence"
        ]
        substrate_summary["entities_created"] += network_projection["entities_created"]
        substrate_summary["relations_created"] += network_projection["relations_created"]
        substrate_summary["entities_created"] += (
            public_services_projection["provider_entities_created"]
            + public_services_projection["listing_entities_created"]
        )
        substrate_summary["relations_created"] += public_services_projection["relations_created"]
        substrate_summary["events_created"] += public_services_projection["events_created"]
        substrate_summary["public_services_projected"] = (
            public_services_projection["provider_entities_created"]
            + public_services_projection["listing_entities_created"]
        )
        substrate_summary["public_services_unresolved"] = (
            public_services_projection["unresolved_service_listings"]
            + public_services_projection["unactivated_types"]
        )
        substrate_summary["substrate_evidence_created"] = public_services_projection["evidence_created"]
        substrate_summary["capabilities_created"] = tool_capability_projection["created"]
        substrate_summary["capabilities_refreshed"] = tool_capability_projection["refreshed"]
        substrate_summary["capability_events_created"] = tool_capability_projection["events_created"]
        substrate_summary["entities_created"] += legacy_record_projection["entities_created"]
        substrate_summary["events_created"] += legacy_record_projection["events_created"]
        substrate_summary["legacy_records_projected"] = legacy_record_projection["entities_created"]
        substrate_summary["legacy_records_unresolved"] = legacy_record_projection["unresolved_records"]
        substrate_summary["entities_created"] += legacy_evidence_projection["entities_created"]
        substrate_summary["legacy_evidence_mapped"] = legacy_evidence_projection["records_mapped"]
        substrate_summary["legacy_evidence_unresolved"] = legacy_evidence_projection["unresolved_records"]
        substrate_summary["legacy_evidence_batch_seen"] = legacy_evidence_projection["records_seen"]
        substrate_summary["entities_created"] += evidence_relationship_projection["entities_created"]
        substrate_summary["relations_created"] += evidence_relationship_projection["relations_created"]
        substrate_summary["evidence_relationships_projected"] = evidence_relationship_projection["relations_created"]
        substrate_summary["evidence_relationships_unresolved"] = evidence_relationship_projection["unresolved_records"]
        substrate_summary["entities_created"] += research_question_relation_projection["entities_created"]
        substrate_summary["relations_created"] += research_question_relation_projection["relations_created"]
        substrate_summary["research_question_relations_projected"] = research_question_relation_projection["relations_created"]
        substrate_summary["research_question_relations_unresolved"] = research_question_relation_projection["unresolved_links"]
        substrate_summary["research_task_events_projected"] = research_task_event_projection["events_projected"]
        substrate_summary["research_task_events_unresolved"] = research_task_event_projection["unresolved_events"]
        substrate_summary["events_created"] += research_task_event_projection["events_projected"]
        market_signal_projection = market_signal_substrate_adapter.sync_market_signal_signals(db, limit=250)
        substrate_summary["market_signal_signals_seen"] = market_signal_projection["signals_seen"]
        substrate_summary["market_signal_entities_created"] = market_signal_projection["entities_created"]
        substrate_summary["market_signal_relations_created"] = market_signal_projection["relations_created"]
        substrate_summary["market_signal_events_created"] = market_signal_projection["events_created"]
        substrate_summary["market_signal_evidence_created"] = market_signal_projection["evidence_created"]
        substrate_summary["market_signal_signals_unresolved"] = market_signal_projection["unresolved_signals"]
        substrate_summary["entities_created"] += market_signal_projection["entities_created"]
        substrate_summary["relations_created"] += market_signal_projection["relations_created"]
        substrate_summary["events_created"] += market_signal_projection["events_created"]
        substrate_summary["substrate_evidence_created"] += market_signal_projection["evidence_created"]
        db.commit()
    except Exception as exc:
        stage_errors["substrate_adapters"] = str(exc)
        try:
            db.rollback()
        except Exception:
            pass

    # 10. Money Engine: classify monetization models, flag opportunities
    #    needing revenue validation. Identification only — see
    #    money_engine.run_money_cycle()'s docstring for the boundary.
    money_summary = money_engine.run_money_cycle(db)

    # 11. Autonomy: propose (never execute) low-risk actions for
    #     opportunities needing validation, evaluated against the
    #     owner's AutonomyPolicy. AUTONOMOUS DECISION, not AUTONOMOUS
    #     EXECUTION — see execution_engine.run_autonomous_action_cycle()'s
    #     docstring for exactly why those are different claims.
    autonomy_summary = execution_engine.run_autonomous_action_cycle(db)

    # 11.5. Decision Engine: Propose validation decisions for high-value,
    #       unvalidated opportunities. Each decision is a reasoned proposal
    #       for the next learning step (interviews, landing page, etc.).
    #       Reuses existing suggest_next_experiment_decision() logic.
    decisions_proposed = 0
    try:
        from app.services import decision_engine
        opportunities = (
            db.query(_models.Opportunity)
            .filter(_models.Opportunity.status == "identified")
            .filter(_models.Opportunity.score > 50.0)
            .order_by(_models.Opportunity.score.desc())
            .limit(20)
            .all()
        )
        for opp in opportunities:
            # Check if a decision already exists for this opportunity
            existing_decision = (
                db.query(_models.Decision)
                .filter(_models.Decision.opportunity_id == opp.id)
                .filter(_models.Decision.status.in_(["proposed", "accepted"]))
                .first()
            )
            if not existing_decision:
                decision_engine.suggest_next_experiment_decision(db, opp.id)
                decisions_proposed += 1
    except Exception as exc:
        stage_errors["decision_proposal"] = str(exc)
        # A failed stage must not poison the shared session for the stages
        # that follow (the original 'session in prepared state' failure).
        # Roll back any in-flight transaction before we continue the loop.
        try:
            db.rollback()
        except Exception:
            pass

    # 11.6. Lessons Memory (v2.10): fold any un-consolidated LearningEvents
    #     into the durable Lessons Memory and surface a recall snapshot so
    #     past reality (what was actually learned) is visible in this cycle's
    #     summary — the feed-forward half of "learn like the operator's own
    #     assistant". Reads LearningEvent + writes Lesson only.
    lessons_summary = {"events_total": 0, "new_lessons_or_merges": 0,
                       "lessons_total": 0, "recalled_for_decision": []}
    try:
        from app.services import lessons_engine
        lessons_summary = lessons_engine.run_lessons_cycle(db)
        # recall context for the top unvalidated opportunity, for visibility
        top = (
            db.query(_models.Opportunity)
            .filter(_models.Opportunity.status == "identified")
            .order_by(_models.Opportunity.score.desc())
            .first()
        )
        if top:
            rec = lessons_engine.assist_decision(db, opportunity_id=top.id)
            lessons_summary["recalled_for_decision"] = [
                {"id": l["id"], "theme_key": l["theme_key"], "title": l["title"],
                 "hit_count": l["hit_count"], "summary": l["summary"][:160]}
                for l in rec["recalled_lessons"]
            ]
    except Exception as exc:
        stage_errors["lessons_memory"] = str(exc)
        # Same session-poison guard: a lessons failure must not poison the
        # shared session for the stages that follow.
        try:
            db.rollback()
        except Exception:
            pass

    # 11.7. Orchestrator (v2.11): advance the highest-value unvalidated
    #     opportunities through the canonical flow — accepted decision,
    #     validation Experiment + interview plan, delivery of the
    #     human-executable task. Idempotent: only creates what's missing,
    #     never fabricates a result and never executes anything itself.
    orchestration_summary = {"opportunities_advanced": 0, "stages": [], "pipeline": {}}
    try:
        from app.services import orchestrator
        flow = orchestrator.run_orchestration_flow(db, limit=5, data_scope=data_scope)
        orchestration_summary["opportunities_advanced"] = flow["opportunities_advanced"]
        orchestration_summary["stages"] = [f.get("experiment", {}).get("stage") for f in flow["flow"]]
        orchestration_summary["pipeline"] = flow["pipeline"]
    except Exception as exc:
        stage_errors["orchestration"] = str(exc)
        try:
            db.rollback()
        except Exception:
            pass

    # 12. Scenario Engine (v1.9): a SECONDARY, parallel domain — scans
    #     recent signals for robotics/compute relevance and links any
    #     matches as Evidence against the Phase 1 2036-scenario
    #     indicators. Reads Signal, writes Evidence only; touches
    #     nothing in the Revenue Intelligence pipeline above. See
    #     scenario_engine.run_scenario_engine_cycle()'s docstring.
    #
    #     NON-BLOCKING BY CONSTRUCTION: everything above this point
    #     (Revenue Intelligence, steps 1-11.7) has already run — a failure
    #     here must never turn that real, already-saved work into a 500
    #     response from POST /forge/cycle, nor prevent worker.py from
    #     logging a cycle summary. Same try/except-around-one-unit
    #     pattern collector_runner.py already uses for each individual
    #     collector (see its run_pending_tasks()) — reused here, not
    #     invented fresh.
    try:
        scenario_summary = scenario_engine.run_scenario_engine_cycle(db)
    except Exception as exc:
        scenario_summary = {"status": "failed", "reason": str(exc), "signals_reviewed": 0, "signals_classified": 0}
    else:
        scenario_summary["status"] = "completed"

    # Propose actions from recent accepted decisions (policy-gated)
    actions_proposed = 0
    try:
        from app.services import action_engine, decision_engine
        recent_decisions = (
            db.query(_models.Decision)
            .filter(_models.Decision.status == "accepted")
            .order_by(_models.Decision.decided_at.desc())
            .limit(5)
            .all()
        )
        for d in recent_decisions:
            existing = db.query(_models.Action).filter_by(decision_id=d.id).count()
            if existing == 0:
                created = action_engine.actions_from_decision(db, d.id, count=1)
                actions_proposed += len(created)
    except Exception as exc:
        stage_errors["action_proposal"] = str(exc)
        # Same session-poison guard as decision_proposal: roll back so the
        # final summary query + commit below can still run cleanly.
        try:
            db.rollback()
        except Exception:
            pass

    # Side step: review recorded paid offers. It does not contact anyone,
    # move money, or treat a stated price as a new sale.
    revenue_miner_summary = {"proposals_created": 0, "executed": False}
    try:
        from app.services.revenue_miner import mine_revenue_proposals

        revenue_miner_summary["proposals_created"] = len(mine_revenue_proposals(db))
    except Exception as exc:
        stage_errors["revenue_miner"] = str(exc)
        try:
            db.rollback()
        except Exception:
            pass

    summary = {
        "signals_processed": signals_processed,
        "source_addresses_restored": source_addresses_restored,
        "claims_linked": linked_claim_ids,
        "network_connection_ids": network_connection_ids,
        "patterns_found": len(patterns),
        "substrate_entities_created": substrate_summary["entities_created"],
        "substrate_relations_created": substrate_summary["relations_created"],
        "substrate_events_created": substrate_summary["events_created"],
        "substrate_ambiguous_legacy_links": substrate_summary["ambiguous_links"],
        "substrate_network_connections_projected": substrate_summary["network_connections_projected"],
        "substrate_network_connections_unresolved": substrate_summary["network_connections_unresolved"],
        "substrate_network_truth_waiting_for_evidence": substrate_summary["network_truth_waiting_for_evidence"],
        "substrate_public_services_projected": substrate_summary["public_services_projected"],
        "substrate_public_services_unresolved": substrate_summary["public_services_unresolved"],
        "substrate_evidence_created": substrate_summary["substrate_evidence_created"],
        "substrate_capabilities_created": substrate_summary["capabilities_created"],
        "substrate_capabilities_refreshed": substrate_summary["capabilities_refreshed"],
        "substrate_capability_events_created": substrate_summary["capability_events_created"],
        "substrate_legacy_records_projected": substrate_summary["legacy_records_projected"],
        "substrate_legacy_records_unresolved": substrate_summary["legacy_records_unresolved"],
        "substrate_legacy_evidence_mapped": substrate_summary["legacy_evidence_mapped"],
        "substrate_legacy_evidence_unresolved": substrate_summary["legacy_evidence_unresolved"],
        "substrate_legacy_evidence_batch_seen": substrate_summary["legacy_evidence_batch_seen"],
        "substrate_evidence_relationships_projected": substrate_summary["evidence_relationships_projected"],
        "substrate_evidence_relationships_unresolved": substrate_summary["evidence_relationships_unresolved"],
        "substrate_research_question_relations_projected": substrate_summary["research_question_relations_projected"],
        "substrate_research_question_relations_unresolved": substrate_summary["research_question_relations_unresolved"],
        "substrate_research_task_events_projected": substrate_summary["research_task_events_projected"],
        "substrate_research_task_events_unresolved": substrate_summary["research_task_events_unresolved"],
        "beliefs_updated": beliefs_updated,
        "predictions_created": predictions_created,
        "predictions_resolved": len(resolved_predictions),
        "questions_created": len(new_questions),
        "research_tasks_created": len(new_tasks),
        "rare_signals_detected": len(rare_assessments),
        "rare_signal_research_questions": len(rare_questions),
        "patterns_reviewed_for_opportunities": discovery_summary["patterns_reviewed"],
        "opportunities_discovered": discovery_summary["opportunities_created"] + discovery_summary.get("single_signal_opportunities_created", 0),
        "opportunity_questions_linked": opportunity_questions_linked,
        "pattern_opportunities_created": discovery_summary["opportunities_created"],
        "single_signal_opportunities_created": discovery_summary.get("single_signal_opportunities_created", 0),
        "single_strong_signals_scanned": discovery_summary.get("single_strong_signals_scanned", 0),
        "patterns_without_sufficient_evidence": discovery_summary["patterns_without_sufficient_evidence"],
        "opportunities_classified": money_summary["opportunities_classified"],
        "opportunities_needing_validation": money_summary["opportunities_needing_validation"],
        "actions_proposed": autonomy_summary.get("proposed", 0),
        "actions_allowed": autonomy_summary.get("allowed", 0),
        "actions_requiring_approval": autonomy_summary.get("require_approval", 0),
        "actions_blocked": autonomy_summary.get("blocked", 0),
        "scenario": scenario_summary,
        "lessons_memory": lessons_summary,
        "orchestration": orchestration_summary,
        "actions_from_decisions": actions_proposed,
        "revenue_miner": revenue_miner_summary,
        "stage_errors": stage_errors,
        "cycle_id": cycle.id,
    }
    cycle.ended_at = datetime.now(timezone.utc)
    if cycle.started_at:
        start = cycle.started_at
        end = cycle.ended_at
        # Normalize tz-awareness for SQLite round-trips
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        cycle.duration_ms = int((end - start).total_seconds() * 1000)
    cycle.status = "FAILED" if stage_errors else "COMPLETED"
    cycle.summary_json = json.dumps(summary, default=str)
    if stage_errors:
        cycle.error = "; ".join(f"{k}: {v}" for k, v in stage_errors.items())
    db.commit()
    return summary


def _parse_signal_ids(raw: Optional[str]) -> list[int]:
    if not raw:
        return []
    return [int(part) for part in raw.split(",") if part.strip().isdigit()]


# ---------------------------------------------------------------------
# Automatic scheduling now lives in backend/worker.py — a separate
# process that calls run_cycle() (and collector_runner.run_pending_tasks())
# on an interval. It's a separate process rather than a `while True`
# loop in this file because a real background loop inside the FastAPI
# process would block incoming API requests; running it externally
# means it can never do that, and both processes just share the same
# SQLite file.
# ---------------------------------------------------------------------
