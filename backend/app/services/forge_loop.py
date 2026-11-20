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
    9.6 Capacity gates                 -> evaluate the local SFU TEST chain
                                          from recorded evidence and stage
                                          internal proposals only
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
(opportunity_claim_questions, substrate_adapters, capacity_gate_tick, decision_proposal,
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

import hashlib
import json
from pathlib import Path
import tempfile
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import settings
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


_CAPACITY_GATE_DEFINITIONS = (
    {
        "gate_id": "sfu-1000-baseline",
        "display_name": "SFU 1,000-viewer local baseline",
        "required_evidence": [{
            "evidence_id": "20x50_pass",
            "description": "A full local 20-publisher by 50-viewer measurement gate passes.",
        }],
    },
    {
        "gate_id": "sfu-1500-frame-integrity",
        "display_name": "SFU 1,500-viewer frame integrity",
        "required_evidence": [{
            "evidence_id": "20x75_frame_integrity_pass",
            "description": "Every selected RTP timestamp reconciles at every viewer.",
        }],
    },
    {
        "gate_id": "sfu-1500-cause",
        "display_name": "SFU 1,500-viewer frame cause",
        "required_evidence": [{
            "evidence_id": "frame_cause_localized",
            "description": "The packet and assembler evidence accounts for each missing frame.",
        }],
    },
    {
        "gate_id": "sfu-safe-copy-treatment",
        "display_name": "SFU safe packet-copy treatment",
        "required_evidence": [{
            "evidence_id": "nack_regression_passed",
            "description": "NACK, PLI, FIR, retransmission, and viewer delivery all pass.",
        }],
    },
    {
        "gate_id": "sfu-1500-repeat",
        "display_name": "SFU 1,500-viewer repeat",
        "required_evidence": [
            {
                "evidence_id": "20x75_repeat_pass",
                "description": "A matched 20-by-75 repeat passes the full per-viewer gate.",
            },
            {
                "evidence_id": "host_headroom_verified",
                "description": "Host headroom is above the recorded safety floor before the run.",
            },
        ],
    },
)
_CAPACITY_GATE_DEPENDENCIES = (
    ("sfu-1500-frame-integrity", "sfu-1000-baseline"),
    ("sfu-1500-cause", "sfu-1500-frame-integrity"),
    ("sfu-safe-copy-treatment", "sfu-1000-baseline"),
    ("sfu-1500-repeat", "sfu-1500-cause"),
    ("sfu-1500-repeat", "sfu-safe-copy-treatment"),
)
_CAPACITY_GATE_ACTION_OBJECTIVES = {
    "sfu-1500-frame-integrity": (
        "Add bounded RTP/frame-assembler diagnostics for the known timestamps; "
        "do not start the 20x75 run until free swap is at least 2048 MiB."
    ),
    "sfu-1500-cause": (
        "Use retained RTP sequence and assembler evidence to localize each missing frame; "
        "do not start a scale run."
    ),
    "sfu-safe-copy-treatment": (
        "Assess a Pion packet-copy treatment behind the existing NACK/PLI/FIR and "
        "viewer-retransmission regression; do not start a scale run."
    ),
    "sfu-1500-repeat": (
        "Verify host headroom and prepare a matched 20x75 repeat only; require at least "
        "2048 MiB free swap and an owner-started run."
    ),
}


def _local_gate_results(
    db: Session,
    gate: models.SubstrateEntity,
) -> tuple[str, list[int], int]:
    required = json.loads(gate.attributes)["required_evidence"]
    required_keys = {item["evidence_key"] for item in required}
    matching: dict[str, list[models.WorldEvent]] = {key: [] for key in required_keys}
    rejected_events = 0
    for row in (
        db.query(models.WorldEvent)
        .filter_by(entity_id=gate.id, event_type="capacity_gate_result")
        .order_by(models.WorldEvent.id.asc())
        .all()
    ):
        try:
            payload = json.loads(row.payload or "{}")
        except (TypeError, json.JSONDecodeError):
            rejected_events += 1
            continue
        if not isinstance(payload, dict):
            rejected_events += 1
            continue
        evidence_key = payload.get("evidence_key")
        if (
            not isinstance(evidence_key, str)
            or evidence_key not in matching
            or payload.get("gate_key") != json.loads(gate.attributes)["gate_key"]
            or row.source != "sfu-single"
        ):
            rejected_events += 1
            continue
        artifact_ref = payload.get("artifact_ref")
        artifact_digest = payload.get("artifact_sha256")
        revision = payload.get("revision")
        if (
            payload.get("data_scope") != "TEST"
            or payload.get("environment") != "local"
            or not isinstance(payload.get("run_id"), str)
            or not payload["run_id"].strip()
            or not isinstance(payload.get("command"), str)
            or not payload["command"].strip()
            or payload.get("result") not in {"passed", "failed"}
            or not isinstance(revision, str)
            or not 7 <= len(revision) <= 40
            or any(character not in "0123456789abcdef" for character in revision)
            or not isinstance(artifact_digest, str)
            or len(artifact_digest) != 64
            or any(character not in "0123456789abcdef" for character in artifact_digest)
            or not isinstance(artifact_ref, str)
            or not Path(artifact_ref).is_absolute()
        ):
            rejected_events += 1
            continue
        try:
            artifact_path = Path(artifact_ref).resolve(strict=True)
            artifact_root = Path(tempfile.gettempdir()).resolve()
            artifact_path.relative_to(artifact_root)
            if (
                not artifact_path.name.startswith("hami-capacity-gate-result-")
                or artifact_path.suffix != ".json"
                or not artifact_path.is_file()
                or artifact_path.stat().st_size > 64 * 1024 * 1024
            ):
                rejected_events += 1
                continue
            artifact_bytes = artifact_path.read_bytes()
            if len(artifact_bytes) > 64 * 1024 * 1024:
                rejected_events += 1
                continue
            artifact = json.loads(artifact_bytes.decode("utf-8"))
            actual_digest = hashlib.sha256(artifact_bytes).hexdigest()
        except (
            OSError,
            RuntimeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            rejected_events += 1
            continue
        if (
            actual_digest != artifact_digest
            or not isinstance(artifact, dict)
            or any(
                artifact.get(field) != payload.get(field)
                for field in (
                    "gate_key", "evidence_key", "data_scope", "environment",
                    "run_id", "revision", "command", "result",
                )
            )
        ):
            rejected_events += 1
            continue
        matching[evidence_key].append(row)

    result_event_ids = sorted(row.id for rows in matching.values() for row in rows)
    if any(json.loads(row.payload).get("result") == "failed" for rows in matching.values() for row in rows):
        return "BLOCKED", result_event_ids, rejected_events
    passed_keys = {
        key for key, rows in matching.items()
        if any(
            json.loads(row.payload).get("result") == "passed"
            for row in rows
        )
    }
    if len(passed_keys) == len(required_keys):
        return "PROVEN", result_event_ids, rejected_events
    if result_event_ids:
        return "IN_PROGRESS", result_event_ids, rejected_events
    return "UNKNOWN", result_event_ids, rejected_events


def run_capacity_gate_tick(db: Session) -> dict:
    """Re-evaluate the existing SFU gate chain from local TEST evidence only."""
    from app import models
    from app.services import action_engine, world_graph

    world_graph.seed_core_types(db)
    gates: dict[str, models.SubstrateEntity] = {}
    created_gates = 0
    for definition in _CAPACITY_GATE_DEFINITIONS:
        gate_key = definition["gate_id"]
        required_evidence = [
            {
                "evidence_key": item["evidence_id"],
                "description": item["description"],
            }
            for item in definition["required_evidence"]
        ]
        identity_key = f"source:gate:forge_gate_definition:{gate_key}"
        if db.query(models.SubstrateEntity.id).filter_by(identity_key=identity_key).first() is None:
            created_gates += 1
        gates[gate_key] = world_graph.create_entity(
            db,
            entity_type="gate",
            display_name=definition["display_name"],
            attributes={
                "gate_key": gate_key,
                "required_evidence": required_evidence,
            },
            created_by="forge_gate_tick",
            identity={
                "source_system": "forge_gate_definition",
                "source_id": gate_key,
                "provenance": {
                    "definition": "forge_loop.capacity_gate_definitions",
                    "gate_key": gate_key,
                },
            },
        )

    created_relations = 0
    for dependent_key, prerequisite_key in _CAPACITY_GATE_DEPENDENCIES:
        idempotency_key = f"capacity-gate-dependency:{dependent_key}:{prerequisite_key}"
        if db.query(models.WorldRelation.id).filter_by(idempotency_key=idempotency_key).first() is None:
            created_relations += 1
        world_graph.create_relation(
            db,
            from_entity_id=gates[dependent_key].id,
            to_entity_id=gates[prerequisite_key].id,
            relation_type="depends_on",
            attributes={"source": "capacity_gate_definition"},
            created_by="forge_gate_tick",
            idempotency_key=idempotency_key,
        )

    gate_ids = {gate.id for gate in gates.values()}
    gate_key_by_id = {gate.id: gate_key for gate_key, gate in gates.items()}
    dependencies_by_key: dict[str, list[str]] = {
        gate_key: [] for gate_key in gates
    }
    for relation in (
        db.query(models.WorldRelation)
        .filter(
            models.WorldRelation.relation_type == "depends_on",
            models.WorldRelation.from_entity_id.in_(gate_ids),
            models.WorldRelation.to_entity_id.in_(gate_ids),
        )
        .order_by(models.WorldRelation.id.asc())
        .all()
    ):
        dependent_key = gate_key_by_id[relation.from_entity_id]
        prerequisite_key = gate_key_by_id[relation.to_entity_id]
        dependencies_by_key[dependent_key].append(prerequisite_key)

    evidence_states: dict[str, tuple[str, list[int], int]] = {
        gate_key: _local_gate_results(db, gate)
        for gate_key, gate in gates.items()
    }
    states: dict[str, str] = {}
    transition_event_ids: dict[str, int | None] = {}
    events_created = 0
    for definition in _CAPACITY_GATE_DEFINITIONS:
        gate_key = definition["gate_id"]
        gate = gates[gate_key]
        evidence_state, result_event_ids, rejected_events = evidence_states[gate_key]
        dependencies = {
            prerequisite_key: states.get(prerequisite_key, "UNKNOWN")
            for prerequisite_key in dependencies_by_key[gate_key]
        }
        if "BLOCKED" in dependencies.values():
            state = "BLOCKED"
        elif evidence_state == "PROVEN" and any(state != "PROVEN" for state in dependencies.values()):
            state = "IN_PROGRESS"
        else:
            state = evidence_state
        states[gate_key] = state

        prior_event = (
            db.query(models.WorldEvent)
            .filter_by(entity_id=gate.id, event_type="gate_evaluated")
            .order_by(models.WorldEvent.id.desc())
            .first()
        )
        prior_payload = json.loads(prior_event.payload) if prior_event else {}
        prior_state = prior_payload.get("state", "UNKNOWN")
        state_changed = prior_state != state
        dependency_signature = ",".join(
            f"{key}={value}" for key, value in sorted(dependencies.items())
        )
        event_key = (
            f"capacity-gate-evaluation:{gate_key}:{prior_state}->{state}:"
            f"{','.join(str(event_id) for event_id in result_event_ids)}:"
            f"rejected={rejected_events}:{dependency_signature}"
        )
        if db.query(models.WorldEvent.id).filter_by(idempotency_key=event_key).first() is None:
            events_created += 1
        evaluation_event = world_graph.create_event(
            db,
            event_type="gate_evaluated",
            source="forge_gate_tick",
            entity_id=gate.id,
            payload={
                "gate_key": gate_key,
                "previous_state": prior_state,
                "state": state,
                "state_changed": state_changed,
                "result_event_ids": result_event_ids,
                "rejected_result_events": rejected_events,
                "dependency_states": dependencies,
                "data_scope": "TEST",
            },
            idempotency_key=event_key,
        )
        if state == "PROVEN":
            if state_changed:
                transition_event_ids[gate_key] = evaluation_event.id
            else:
                transition_event_ids[gate_key] = _latest_proven_gate_transition_id(
                    db,
                    gate.id,
                )
        else:
            transition_event_ids[gate_key] = None

    actions_proposed = 0
    for dependent_key, prerequisite_keys in dependencies_by_key.items():
        dependent_state = states[dependent_key]
        if (
            not prerequisite_keys
            or dependent_state not in {"UNKNOWN", "IN_PROGRESS"}
            or any(states[key] != "PROVEN" for key in prerequisite_keys)
        ):
            continue
        prerequisite_event_ids = {
            key: transition_event_ids[key]
            for key in prerequisite_keys
        }
        if any(event_id is None for event_id in prerequisite_event_ids.values()):
            continue
        if _existing_gate_transition_action(
            db,
            gates[dependent_key].id,
            prerequisite_event_ids,
        ):
            continue
        action_engine.propose_action(
            db,
            action_type="research",
            objective=_CAPACITY_GATE_ACTION_OBJECTIVES[dependent_key],
            parameters={
                "data_scope": "TEST",
                "gate_key": dependent_key,
                "gate_entity_id": gates[dependent_key].id,
                "trigger_event_ids": prerequisite_event_ids,
                "trigger_gate_keys": prerequisite_keys,
                "execution_boundary": "proposal_only",
                "requires_owner_to_start": True,
            },
            estimated_cost=0.0,
            risk_score=0.0,
        )
        actions_proposed += 1

    return {
        "gates_created": created_gates,
        "relations_created": created_relations,
        "gate_evaluations_created": events_created,
        "gate_states": states,
        "unverified_result_events": sum(item[2] for item in evidence_states.values()),
        "actions_proposed": actions_proposed,
        "executed": False,
    }


def _latest_proven_gate_transition_id(db: Session, gate_entity_id: int) -> int | None:
    from app import models

    events = (
        db.query(models.WorldEvent)
        .filter_by(entity_id=gate_entity_id, event_type="gate_evaluated")
        .order_by(models.WorldEvent.id.desc())
        .all()
    )
    for event in events:
        payload = json.loads(event.payload)
        if payload.get("state") == "PROVEN" and payload.get("state_changed") is True:
            return event.id
    return None


def _existing_gate_transition_action(
    db: Session,
    gate_entity_id: int,
    trigger_event_ids: dict[str, int | None],
) -> bool:
    actions = db.query(models.Action).filter_by(action_type="research").all()
    for action in actions:
        try:
            parameters = json.loads(action.parameters_json or "{}")
        except json.JSONDecodeError:
            continue
        if (
            isinstance(parameters, dict)
            and parameters.get("gate_entity_id") == gate_entity_id
            and parameters.get("trigger_event_ids") == trigger_event_ids
        ):
            return True
    return False


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

    # 6. Automatic question generation stays paused by default while the
    # existing backlog is reviewed. Existing, owner/user-supplied questions
    # remain available to the planner; no new vague template questions are added.
    question_generation_enabled = settings.FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED
    new_questions = []
    if question_generation_enabled:
        ce = curiosity_engine.CuriosityEngine(db)
        new_questions = ce.run_curiosity_scan()

    # 7. Plan research tasks for existing open questions
    new_tasks = research_planner.plan_tasks_for_open_questions(db)

    # 8. Rare Signal Detection (v2.6): persist explainable weak-signal
    # assessments and route high-scoring ones into the existing P1
    # research planner. Detection is heuristic; no opportunity is made
    # here and no score is treated as truth.
    rare_assessments = rare_signal_engine.detect_rare_signals(db)
    rare_questions = (
        rare_signal_engine.trigger_research_for_rare_signals(db, rare_assessments)
        if question_generation_enabled
        else []
    )

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
    if question_generation_enabled:
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

    gate_tick_summary = {
        "gates_created": 0,
        "relations_created": 0,
        "gate_evaluations_created": 0,
        "gate_states": {},
        "actions_proposed": 0,
        "executed": False,
    }
    try:
        gate_tick_summary = run_capacity_gate_tick(db)
        db.commit()
    except Exception as exc:
        stage_errors["capacity_gate_tick"] = str(exc)
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
        "capacity_gate_tick": gate_tick_summary,
        "beliefs_updated": beliefs_updated,
        "predictions_created": predictions_created,
        "predictions_resolved": len(resolved_predictions),
        "questions_created": len(new_questions),
        "research_tasks_created": len(new_tasks),
        "rare_signals_detected": len(rare_assessments),
        "rare_signal_research_questions": len(rare_questions),
        "question_generation": (
            "enabled" if question_generation_enabled else "paused_backlog_review"
        ),
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
