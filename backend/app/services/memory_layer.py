"""
FORGE MEMORY LAYER
====================

Forge's permanent, retrievable knowledge store — separate from the
Signals table (raw, transient observations) and built on top of
Belief/Pattern (which already exist for reasoning). A Knowledge row is
never created directly by a user or an API call; it's always a synced,
embedded snapshot of a Belief's or Pattern's current statement, kept
current by belief_engine.py and pattern_engine.py whenever the source
changes (form_belief_from_pattern, adjust_confidence, and
run_pattern_detection all call sync_* below).

This is what gets searched before an AI provider — including a local
Ollama model — answers a question, so Forge grounds its answers in its
own accumulated, evidence-linked reasoning instead of the model's
general training data. See ai_engine.answer_question().

Search is brute-force cosine similarity in pure Python (see
embedding_engine.py) — appropriate for a personal, locally-run
knowledge base, and keeps the $0/no-new-dependency principle intact
(no vector database, no numpy/faiss).
"""


from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services import embedding_engine
from typing import Optional




def _upsert(
    db: Session,
    source_type: str,
    source_id: int,
    title: str,
    content: str,
    confidence_score: float,
    category: Optional[str] = None,
) -> models.Knowledge:
    """Create or update the Knowledge row for a given (source_type,
    source_id). Re-embeds only when the content actually changed, since
    embedding a hash vector is cheap but an Ollama embedding call isn't
    free in time even if it's free in money."""
    existing = (
        db.query(models.Knowledge)
        .filter(models.Knowledge.source_type == source_type, models.Knowledge.source_id == source_id)
        .first()
    )

    if existing and existing.content == content:
        # Content unchanged — just keep confidence current, skip re-embedding.
        existing.confidence_score = confidence_score
        existing.updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    vector, model_name = embedding_engine.get_embedding(content)
    embedding_json = embedding_engine.serialize_embedding(vector)

    if existing:
        existing.title = title
        existing.content = content
        existing.category = category
        existing.confidence_score = confidence_score
        existing.embedding = embedding_json
        existing.embedding_model = model_name
        existing.updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    knowledge = models.Knowledge(
        title=title,
        content=content,
        category=category,
        source_type=source_type,
        source_id=source_id,
        confidence_score=confidence_score,
        embedding=embedding_json,
        embedding_model=model_name,
    )
    db.add(knowledge)
    db.commit()
    db.refresh(knowledge)
    return knowledge


def sync_belief_to_knowledge(db: Session, belief: models.Belief) -> models.Knowledge:
    """Sync a Belief's current statement + confidence into permanent
    Knowledge. Called whenever a belief is formed or its confidence
    changes (belief_engine.py)."""
    title = belief.statement[:80] + ("…" if len(belief.statement) > 80 else "")
    return _upsert(
        db,
        source_type="belief",
        source_id=belief.id,
        title=title,
        content=belief.statement,
        confidence_score=belief.confidence_score,
    )


def sync_pattern_to_knowledge(db: Session, pattern: models.Pattern) -> models.Knowledge:
    """Sync a Pattern's title/description + confidence into permanent
    Knowledge. Called whenever a pattern is detected (pattern_engine.py)."""
    return _upsert(
        db,
        source_type="pattern",
        source_id=pattern.id,
        title=pattern.title,
        content=pattern.description,
        confidence_score=pattern.confidence_score,
    )


def search_knowledge(
    db: Session, query_text: str, top_k: int = 5, source_type: Optional[str] = None
) -> list[tuple[models.Knowledge, float]]:
    """Semantic search over Knowledge: embed the query with the
    CURRENTLY configured provider, and compare only against stored
    entries that share that same embedding_model (different models'
    vectors aren't comparable — see embedding_engine.py). Returns
    (Knowledge, similarity) pairs, highest similarity first."""
    query_vector, query_model = embedding_engine.get_embedding(query_text)

    rows_query = db.query(models.Knowledge).filter(models.Knowledge.embedding_model == query_model)
    if source_type:
        rows_query = rows_query.filter(models.Knowledge.source_type == source_type)
    rows = rows_query.all()
    hidden_ids = _hidden_belief_ids(db)
    rows = [
        row
        for row in rows
        if row.source_type != "belief" or row.source_id not in hidden_ids
    ]

    scored = []
    for row in rows:
        vector = embedding_engine.deserialize_embedding(row.embedding)
        similarity = embedding_engine.cosine_similarity(query_vector, vector)
        if similarity > 0:
            scored.append((row, similarity))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def retrieve_context_for_prompt(db: Session, query_text: str, top_k: int = 3) -> str:
    """Format the top matching Knowledge entries as a short context
    block ready to prepend to an AI prompt. Empty string if nothing
    relevant is found (e.g. an empty knowledge base) — callers should
    treat that as "no memory available", not an error."""
    matches = search_knowledge(db, query_text, top_k=top_k)
    if not matches:
        return ""

    lines = [
        f"- ({knowledge.source_type}, confidence {knowledge.confidence_score:.0f}%) {knowledge.content}"
        for knowledge, _similarity in matches
    ]
    return "Forge's relevant existing knowledge:\n" + "\n".join(lines)


def list_knowledge(db: Session, source_type: Optional[str] = None, limit: int = 100) -> list[models.Knowledge]:
    query = db.query(models.Knowledge)
    if source_type:
        query = query.filter(models.Knowledge.source_type == source_type)
    rows = query.order_by(models.Knowledge.updated_at.desc()).all()
    hidden_ids = _hidden_belief_ids(db)
    rows = [
        row
        for row in rows
        if row.source_type != "belief" or row.source_id not in hidden_ids
    ]
    return rows[:limit]


def _hidden_belief_ids(db: Session) -> set[int]:
    from app.services.belief_engine import is_presentable_belief
    return {
        belief.id
        for belief in db.query(models.Belief).all()
        if not is_presentable_belief(belief)
    }
