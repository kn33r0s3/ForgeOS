from app import models
from app.services import research_planner


def test_gap_questions_are_not_planned_for_external_collectors(db):
    gap = models.ResearchQuestion(
        question='Gap: open job #1 "repair" has no recorded counterparty.'
    )
    normal = models.ResearchQuestion(question="What evidence describes repair demand?")
    db.add_all([gap, normal])
    db.commit()

    tasks = research_planner.plan_tasks_for_open_questions(db)

    assert tasks
    assert all(task.question_id == normal.id for task in tasks)
    assert db.query(models.ResearchTask).filter_by(question_id=gap.id).count() == 0
    assert db.get(models.ResearchQuestion, gap.id).status == "open"
