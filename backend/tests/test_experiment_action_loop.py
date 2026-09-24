from app import models
from app.services import experiment_action_service


def _authorized_experiment(db):
    experiment = models.Experiment(
        opportunity_id=None,
        action="Contact the research participants",
        action_type="research",
        hypothesis="Participants will confirm the problem.",
        expected_result="A response is recorded from the participants.",
        authorization_status="allowed",
        authorized_at=models.utcnow(),
        approved_at=models.utcnow(),
        execution_status="authorized",
        response_received="none",
        revenue_amount=0.0,
        revenue_currency="USD",
        status="planned",
        requires_owner_approval=True,
        execution_allowed=True,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def test_adapter_success_is_separate_from_business_outcome_and_learning(db):
    experiment = _authorized_experiment(db)

    proposed = experiment_action_service.propose_action(db, experiment.id)
    executed = experiment_action_service.execute_action(db, experiment.id)

    assert proposed["experiment_id"] == experiment.id
    assert executed["status"] == "SUCCEEDED"
    assert executed["verification_state"] == "UNVERIFIED"
    assert db.query(models.Outcome).count() == 0
    assert db.query(models.LearningEvent).count() == 0
    assert db.query(models.Lesson).count() == 0

    result = experiment_action_service.record_actual_response(
        db,
        experiment.id,
        actual="Participants rejected the proposed workflow.",
        success=False,
        source="human_interview",
    )

    outcome = result["outcome"]
    learning = result["learning"]
    refreshed_action = db.get(models.Action, proposed["id"])
    refreshed_experiment = db.get(models.Experiment, experiment.id)

    assert outcome.action_id == refreshed_action.id
    assert outcome.experiment_id == experiment.id
    assert outcome.actual_value is None
    assert outcome.verification_state == "REPORTED"
    assert learning.experiment_id == experiment.id
    assert refreshed_action.status == "VERIFIED"
    assert refreshed_action.verification_state == "VERIFIED_FAILURE"
    assert refreshed_experiment.status == "completed"
    assert refreshed_experiment.execution_status == "completed"
    assert refreshed_experiment.revenue_amount == 0.0
    assert refreshed_experiment.revenue is None
    assert db.query(models.Lesson).count() == 1