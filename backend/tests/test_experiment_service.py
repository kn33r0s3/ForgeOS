from app import models
from app.schemas.experiment import ExperimentAuthorize, ExperimentProposalCreate
from app.services import experiment_service


def test_proposed_experiment_is_research_first_and_requires_approval(db):
    payload = ExperimentProposalCreate(
        source_analyze_id=7,
        source_signal_id=11,
        source_research_question_id=13,
        source_research_task_ids=[101, 102],
        problem_statement="Customers churn when onboarding is unclear",
        hypothesis="Short onboarding explains churn",
        evidence_summary="Two support signals and one research question",
        target="Early SaaS customers",
        offer="A guided onboarding checklist",
        action_type="research",
        channel="email",
    )

    created = experiment_service.create_proposed(db, payload)

    assert created.opportunity_id is None
    assert created.source_analyze_id == 7
    assert created.authorization_status == "require_approval"
    assert created.execution_status == "proposed"
    assert created.response_received == "none"
    assert created.revenue_amount == 0.0
    assert created.revenue_currency == "USD"
    assert created.status == "planned"
    assert created.requires_owner_approval is True
    assert created.execution_allowed is False

    allowed = experiment_service.authorize_experiment(
        db,
        created.id,
        ExperimentAuthorize(authorization_status="allowed", authorized_by="owner"),
    )
    assert allowed.authorization_status == "allowed"
    assert allowed.execution_status == "authorized"
    assert allowed.authorized_at is not None


def test_mark_executed_updates_execution_and_compat_projection(db):
    experiment = models.Experiment(
        opportunity_id=None,
        action="research",
        source_analyze_id=9,
        authorization_status="allowed",
        authorized_at=models.utcnow(),
        execution_status="proposed",
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

    marked = experiment_service.mark_executed(db, experiment.id)

    assert marked.execution_status == "executed"
    assert marked.executed_at is not None
    assert marked.status == "in_progress"
    assert marked.started_at == marked.executed_at
