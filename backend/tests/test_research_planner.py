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


def test_gap_questions_do_not_fill_the_planning_limit(db):
    for index in range(20):
        db.add(
            models.ResearchQuestion(
                question=f'Gap: open job #{index} "repair" has no recorded counterparty.',
                priority_score=100.0,
                status="open",
            )
        )
    real = models.ResearchQuestion(
        question="What evidence describes repair demand?",
        priority_score=1.0,
        status="open",
    )
    db.add(real)
    db.commit()

    tasks = research_planner.plan_tasks_for_open_questions(db, limit=20)

    assert tasks
    assert all(task.question_id == real.id for task in tasks)
    assert db.get(models.ResearchQuestion, real.id).status == "planned"
    assert db.query(models.ResearchTask).count() == len(tasks)
