"""
EXPERIMENT RUNNER (belief-experiment reports)
=============================================

This legacy path records the owner-reported result of a planned belief test.
The current BeliefExperiment model has no link to a canonical verified Outcome
or Evidence row. Therefore a submitted result and confidence_change are only
a report and a proposed adjustment: they must not update shared Belief
confidence or create reusable CausalKnowledge. Keep the history here; promote
learning only through the existing evidence-backed outcome path.

This is separate from the canonical `Experiment` model, which links to
Outcome and LearningEvent records and has an explicit REAL/verification gate.
"""

import math
from typing import Optional

from sqlalchemy.orm import Session

from app import models


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
        """Persist a reported result without changing shared knowledge.

        `completed` means a result was submitted, not that it was independently
        verified. This model has no canonical Evidence/Outcome link, so the
        supplied confidence_change is retained as a reported proposal only.
        """
        experiment = (
            self.db.query(models.BeliefExperiment)
            .filter(models.BeliefExperiment.id == experiment_id)
            .first()
        )
        if not experiment:
            return None
        if experiment.status == "completed" or experiment.result is not None:
            raise ValueError("Experiment result has already been recorded")
        if not isinstance(result, str) or not result.strip():
            raise ValueError("A non-empty reported result is required")
        if (
            isinstance(confidence_change, bool)
            or not isinstance(confidence_change, (int, float))
            or not math.isfinite(float(confidence_change))
            or not -100.0 <= float(confidence_change) <= 100.0
        ):
            raise ValueError("Reported confidence change must be finite and between -100 and 100")

        experiment.result = result.strip()
        experiment.confidence_change = float(confidence_change)
        experiment.status = "completed"
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def list_experiments(self, belief_id: Optional[int] = None) -> list[models.BeliefExperiment]:
        query = self.db.query(models.BeliefExperiment)
        if belief_id is not None:
            query = query.filter(models.BeliefExperiment.belief_id == belief_id)
        return query.order_by(models.BeliefExperiment.created_at.desc()).all()
