"""
RESEARCH PLANNER
==================

Converts a ResearchQuestion into one or more ResearchTasks — each
tagged with the source it should be investigated on and a query to use
there. Collection itself now happens for real (see
app/services/collectors/ and collector_runner.py); this module only
decides WHICH source(s) a question should be researched on and stores
the resulting tasks for collector_runner to execute (on-demand or via
the Background Forge Worker).

Source selection is a simple keyword-hint match against the question
text (e.g. "software"/"tool" -> github, "customers"/"pain" -> reddit,
"trend"/"market" -> rss, "study"/"paper" -> arxiv), falling back to a
fixed default set of sources if nothing matches. This mirrors the same
free/keyword-over-model tradeoff used everywhere else in Forge.
"""

from sqlalchemy.orm import Session

from app import models
from app.services import research_task_engine

SOURCE_HINTS: dict[str, list[str]] = {
    "github": ["tool", "tools", "software", "code", "automate", "automation", "app", "platform"],
    "reddit": ["customer", "customers", "people", "pain", "complain", "struggle", "avoid", "want"],
    "rss": ["trend", "trends", "market", "industry", "growth", "news", "price", "prices", "currency", "bond", "equity", "commodity", "commodities"],
    "arxiv": ["research", "study", "studies", "paper", "papers", "academic", "science", "evidence"],
}
# These names stay the planning hints. collector_runner fails them
# until docs/PUBLIC_SOURCES.md clears the source. Planning is not collection.
DEFAULT_SOURCES = ["reddit", "github", "rss"]


def _sources_for_question(question_text: str) -> list[str]:
    text = question_text.lower()
    matched = [source for source, hints in SOURCE_HINTS.items() if any(h in text for h in hints)]
    return matched or DEFAULT_SOURCES


def plan_tasks_for_question(db: Session, question: models.ResearchQuestion) -> list[models.ResearchTask]:
    """Create (or return existing) ResearchTasks for one question, one
    per relevant source. Idempotent: re-planning the same question
    won't duplicate tasks for a source it already has a task for."""
    sources = _sources_for_question(question.question)
    created: list[models.ResearchTask] = []

    for source in sources:
        existing = (
            db.query(models.ResearchTask)
            .filter(
                models.ResearchTask.question_id == question.id,
                models.ResearchTask.source == source,
            )
            .first()
        )
        if existing:
            if existing.status == "needs_research":
                research_task_engine.retry_task(db, existing)
                created.append(existing)
            continue
        task = research_task_engine.create_task(
            db,
            question_id=question.id,
            source=source,
            query=question.question.rstrip("?"),
            objective=question.question,
            claim_id=question.source_claim_id,
        )
        created.append(task)

    if created:
        db.commit()
        for task in created:
            db.refresh(task)

    return created


def plan_tasks_for_open_questions(db: Session, limit: int = 20) -> list[models.ResearchTask]:
    """Plan tasks for every currently-open question (used by the Forge
    intelligence cycle). Marks each question "planned" once tasks
    exist for it, so it isn't re-planned every cycle."""
    # Gap questions stay open until a counterparty exists. They must not
    # occupy this limit, or real questions never get planned.
    questions = (
        db.query(models.ResearchQuestion)
        .filter(models.ResearchQuestion.status == "open")
        .filter(~models.ResearchQuestion.question.like("Gap:%"))
        .order_by(models.ResearchQuestion.priority_score.desc())
        .limit(limit)
        .all()
    )

    all_tasks: list[models.ResearchTask] = []
    for question in questions:
        tasks = plan_tasks_for_question(db, question)
        all_tasks.extend(tasks)
        question_tasks = db.query(models.ResearchTask).filter_by(question_id=question.id).all()
        has_pending_or_evidence = any(
            task.status in {"planned", "running"} or bool((task.evidence_ids or "").strip())
            for task in question_tasks
        )
        question.status = "planned" if has_pending_or_evidence else "open"

    db.commit()
    return all_tasks
