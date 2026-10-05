"""
EXPERIMENT RUNNER (belief experiments)
========================================

Runs real-world tests of Beliefs — the strongest form of evidence
Forge can get: not "signals suggest X" but "we tried X and here's what
happened."

    Belief: "Reducing response time increases small business revenue"
        |
        v
    BeliefExperiment: hypothesis + method (e.g. "build an AI phone
                       assistant MVP and measure signups")
        |
        v
    record_result(): result text + confidence_change
        |
        |--> Belief.confidence_score updated via BeliefEngine
        |
        v
    causal_engine.record_causal_outcome(): the raw hypothesis/method/
                       result triple becomes structured, reusable
                       causal knowledge (condition -> action -> outcome)
                       — see causal_engine.py

This is a separate table/flow from the existing `Experiment` model in
models.py, which tests Opportunities (business ideas), not Beliefs
(hypotheses about reality). Keeping them separate avoids overloading
one table with two different meanings — see models.py docstring for
why. Forge doesn't run experiments automatically in v0.1; this module
just gives beliefs a place to be tested and the result fed back in.
"""

from sqlalchemy.orm import Session

from app import models
from app.services import belief_engine, causal_engine
from typing import Optional


class ExperimentRunner:
    def __init__(self, db: Session):
        self.db = db

    def create_experiment(self, belief_id: int, hypothesis: str, method: str) -> models.BeliefExperiment:
        experiment = models.BeliefExperiment(
            belief_id=belief_id,
            hypothesis=hypothesis,
            method=method,
            status="planned",
        )
        self.db.add(experiment)
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def record_result(
        self, experiment_id: int, result: str, confidence_change: float
    ) -> Optional[models.BeliefExperiment]:
        """Record what actually happened, mark the experiment
        completed, and push confidence_change into the linked Belief."""
        experiment = (
            self.db.query(models.BeliefExperiment)
            .filter(models.BeliefExperiment.id == experiment_id)
            .first()
        )
        if not experiment:
            return None
        if experiment.status == "completed":
            raise ValueError("Experiment result has already been recorded")

        experiment.result = result
        experiment.confidence_change = confidence_change
        experiment.status = "completed"
        self.db.commit()
        self.db.refresh(experiment)

        belief = belief_engine.BeliefEngine(self.db).get_belief(experiment.belief_id)
        if belief:
            belief_engine.BeliefEngine(self.db).adjust_confidence(
                belief, confidence_change, reason="experiment", experiment_id=experiment.id
            )
            # Convert the raw hypothesis/method/result triple into
            # structured, reusable causal knowledge — this is the fix
            # for "Forge records experiments but doesn't convert
            # outcomes into reusable causal knowledge" (v0.9). Side
            # effect only; record_result()'s return value/signature is
            # unchanged so nothing calling this API needed to change.
            causal_engine.record_causal_outcome(self.db, experiment, belief)

        return experiment

    def list_experiments(self, belief_id: Optional[int] = None) -> list[models.BeliefExperiment]:
        query = self.db.query(models.BeliefExperiment)
        if belief_id is not None:
            query = query.filter(models.BeliefExperiment.belief_id == belief_id)
        return query.order_by(models.BeliefExperiment.created_at.desc()).all()
