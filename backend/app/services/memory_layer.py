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


import json

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services import embedding_engine
from typing import Optional
from urllib.parse import parse_qsl, urlsplit




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
    """Return retrieved beliefs/patterns with bounded public-source provenance metadata.

    This remains read-only. Source metadata is not source content, claim proof,
    primary-source classification, or independent corroboration.
    """
    matches = search_knowledge(db, query_text, top_k=top_k)
    if not matches:
        return ""

    def parse_signal_ids(raw: str | None) -> list[int]:
        parsed: list[int] = []
        for piece in (raw or "").split(",")[:20]:
            try:
                value = int(piece.strip())
            except (TypeError, ValueError):
                continue
            if value > 0 and value not in parsed:
                parsed.append(value)
        return parsed

    belief_ids = {
        int(knowledge.source_id)
        for knowledge, _similarity in matches
        if knowledge.source_type == "belief" and knowledge.source_id is not None
    }
    pattern_ids = {
        int(knowledge.source_id)
        for knowledge, _similarity in matches
        if knowledge.source_type == "pattern" and knowledge.source_id is not None
    }
    beliefs = (
        db.query(models.Belief).filter(models.Belief.id.in_(belief_ids)).all()
        if belief_ids else []
    )
    patterns = (
        db.query(models.Pattern).filter(models.Pattern.id.in_(pattern_ids)).all()
        if pattern_ids else []
    )
    belief_by_id = {row.id: row for row in beliefs}
    pattern_by_id = {row.id: row for row in patterns}

    signal_ids_by_knowledge: dict[int, list[int]] = {}
    all_signal_ids: set[int] = set()
    for knowledge, _similarity in matches:
        basis_ids: list[int] = []
        if knowledge.source_type == "belief":
            source = belief_by_id.get(knowledge.source_id)
            basis_ids = parse_signal_ids(source.supporting_signal_ids if source else None)
        elif knowledge.source_type == "pattern":
            source = pattern_by_id.get(knowledge.source_id)
            basis_ids = parse_signal_ids(source.origin_signal_ids if source else None)
        signal_ids_by_knowledge[knowledge.id] = basis_ids
        all_signal_ids.update(basis_ids)

    signals = (
        db.query(models.Signal).filter(models.Signal.id.in_(all_signal_ids)).all()
        if all_signal_ids else []
    )
    signal_by_id = {row.id: row for row in signals}
    sensitive_query_keys = {
        "token", "access_token", "api_key", "apikey", "key", "signature",
        "sig", "auth", "authorization", "secret", "password", "session",
    }

    lines = []
    for knowledge, _similarity in matches:
        public_sources: list[dict[str, object]] = []
        for signal_id in signal_ids_by_knowledge.get(knowledge.id, []):
            signal = signal_by_id.get(signal_id)
            if signal is None or signal.source_type != "external":
                continue
            raw_url = (signal.canonical_url or "").strip()
            if not raw_url or len(raw_url) > 2048:
                continue
            try:
                parsed = urlsplit(raw_url)
                query_keys = {key.lower() for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}
            except ValueError:
                continue
            if (
                parsed.scheme.lower() not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or query_keys.intersection(sensitive_query_keys)
            ):
                continue
            public_sources.append({
                "source": str(signal.source or "")[:100] or None,
                "title": str(signal.title or "")[:240] or None,
                "url": raw_url,
                "published_at": signal.published_at.isoformat() if signal.published_at else None,
                "retrieved_at": signal.retrieved_at.isoformat() if signal.retrieved_at else None,
                "collection_status": str(signal.collection_status or "")[:60] or None,
                "source_content_included": False,
            })
            if len(public_sources) >= 3:
                break

        lines.append(
            f"- ({knowledge.source_type}, confidence {knowledge.confidence_score:.0f}%) "
            f"{knowledge.content}\n"
            f"  linked_external_source_metadata_only="
            f"{json.dumps(public_sources, ensure_ascii=False, separators=(',', ':')) if public_sources else '[]'}"
        )

    return (
        "Forge's relevant existing knowledge. Belief/pattern entries are not automatically verified facts. "
        "The linked_external_source_metadata_only field contains bounded metadata from linked external Signals "
        "only; source bodies are not included. A URL, title, date, collection status, confidence score, or "
        "multiple linked records alone does not prove claim truth, primary-source status, freshness of the "
        "underlying facts, or source independence. Missing metadata must remain unknown.\n"
        + "\n".join(lines)
    )


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
