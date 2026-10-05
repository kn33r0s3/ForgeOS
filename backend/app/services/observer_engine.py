"""
OBSERVER ENGINE
================

Forge's "eyes". This is the source-independent entry point for turning
any piece of raw observed information into a stored, scored Signal.

    Observation (any source)
        |
        v
    ObserverEngine.observe()
        |  -> signal_processor: normalize + tag + classify
        |  -> importance_ranker: score 0-100
        |  -> source_manager: snapshot the source's current reliability
        |  -> signal_quality: assess concreteness/coherence/duplication
        |      (v1.4) — Pattern Engine excludes low-quality signals from
        |      clustering, so garbage doesn't confidently propagate into
        |      Patterns/Beliefs/Opportunities. Never discarded — just
        |      flagged, same append-only principle as everywhere else
        |      in Forge.
        v
    Signal row in the database (Signal Memory)
        |
        v
    Pattern Engine (scans QUALITY-GATED signals, finds repeated problems)
        |
        v
    Opportunity Engine

Manual input (via /observer/observe) and real collectors (Reddit,
GitHub, News, Web — see app/services/collectors/ and
collector_runner.py) both end up calling this same observe() method
with a different `source` label — that's what keeps the Pattern Engine
and everything downstream agnostic to where a signal came from, and
what makes quality assessment automatic for every source without
needing to be added to each one individually.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timezone
import hashlib
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError
from app import models
from app.services import signal_processor, importance_ranker, source_manager, signal_quality


class ObserverEngine:
    """
    Responsibilities (per the spec):
      1. Receive raw information.
      2. Convert it into a Forge Signal.
      3. Analyze importance.
      4. Assess quality (concreteness, coherence, duplication) — v1.4.
      5. Store it in memory (the Signals table).
    """

    def __init__(self, db: Session):
        self.db = db

    def observe(
        self,
        content: str,
        source: str = "manual",
        metadata: dict | None = None,
        *,
        persist_evidence: bool = True,
        categorize: bool = True,
    ) -> models.Signal:
        """Process one piece of raw text end-to-end and persist it as a
        fully-scored Signal. This is the one method every observer
        source — manual or collector-driven — should call.

        Blank (whitespace-only) content raises ValueError — the schema
        min_length=1 guard lets "   " through, and an empty Signal row
        would pollute the pool the Pattern Engine reads from."""
        content = content.strip()
        if not content:
            raise ValueError("content must not be empty")
        metadata = metadata or {}
        canonical_url = _normalize_url(metadata.get("canonical_url") or metadata.get("url") or metadata.get("link"))
        external_id = metadata.get("external_id")
        identity_key = metadata.get("identity_key")
        
        # Determine source_type
        source_type = metadata.get("source_type")
        if not source_type:
            if source == "seed" or metadata.get("source") == "seed":
                source_type = "seed"
            elif source == "synthetic" or metadata.get("is_synthetic"):
                source_type = "synthetic"
            elif source == "manual" or metadata.get("source") == "manual":
                source_type = "manual"
            elif source in {"github", "reddit", "rss", "news", "arxiv", "web"}:
                source_type = "external"
            else:
                source_type = "manual"

        retrieved_at = _parse_datetime(metadata.get("retrieved_at") or metadata.get("timestamp"))
        if source_type == "external":
            if not canonical_url:
                raise ValueError("External signal observation requires canonical_url")
            if not retrieved_at:
                retrieved_at = datetime.now(timezone.utc)
            norm_title = (metadata.get("title") or "").strip().lower()
            norm_body = content.strip().lower()
            content_fingerprint = hashlib.sha256(
                f"{canonical_url}:{norm_title}:{norm_body}".encode("utf-8")
            ).hexdigest()
        else:
            retrieved_at = retrieved_at or datetime.now(timezone.utc)
            content_fingerprint = _fingerprint(content)

        previous = None
        if identity_key:
            previous = (
                self.db.query(models.Signal)
                .filter(
                    models.Signal.source == source,
                    models.Signal.identity_key == str(identity_key),
                )
                .order_by(models.Signal.id.desc())
                .first()
            )
        if previous is None and not identity_key and external_id:
            identity_query = self.db.query(models.Signal).filter(models.Signal.source == source)
            previous = identity_query.filter(
                models.Signal.external_id == str(external_id)
            ).order_by(models.Signal.id.desc()).first()
        if previous is None and not identity_key and not external_id and canonical_url:
            identity_query = self.db.query(models.Signal).filter(models.Signal.source == source)
            previous = identity_query.filter(models.Signal.canonical_url == canonical_url).order_by(models.Signal.id.desc()).first()
        if previous is not None and previous.content_fingerprint == content_fingerprint:
            if persist_evidence:
                _ensure_evidence(self.db, previous, metadata)
            return previous

        processed = (
            signal_processor.process_signal(content)
            if categorize
            else {"category": None, "signal_type": "observation", "tags": []}
        )
        importance = importance_ranker.score_importance(content)
        reliability = source_manager.get_reliability(self.db, source)
        quality = signal_quality.assess_quality(
            self.db, content, processed["signal_type"], reliability
        )

        signal = models.Signal(
            source=source,
            source_type=source_type,
            content=content,
            category=processed["category"],
            signal_type=processed["signal_type"],
            importance_score=importance,
            processed=True,
            tags=",".join(processed["tags"]) if processed["tags"] else None,
            reliability_score=reliability,
            freshness_score=100.0,  # fully fresh at observe time; decays conceptually with age
            quality_score=quality["quality_score"],
            quality_flags=",".join(quality["quality_flags"]) if quality["quality_flags"] else None,
            is_duplicate_of=quality["duplicate_of_signal_id"],
            canonical_url=canonical_url,
            external_id=str(external_id) if external_id is not None else None,
            identity_key=str(identity_key) if identity_key is not None else None,
            title=metadata.get("title"),
            published_at=_parse_datetime(metadata.get("published_at") or metadata.get("timestamp")),
            retrieved_at=retrieved_at,
            content_fingerprint=content_fingerprint,
            provenance=json.dumps(metadata.get("provenance"), sort_keys=True) if metadata.get("provenance") else None,
            collection_status=metadata.get("collection_status", "observed"),
            supersedes_signal_id=previous.id if previous is not None else None,
        )
        try:
            if identity_key:
                with self.db.begin_nested():
                    self.db.add(signal)
                    self.db.flush()
            else:
                self.db.add(signal)
            self.db.commit()
            self.db.refresh(signal)
        except IntegrityError:
            self.db.rollback()
            if not identity_key:
                raise
            signal = (
                self.db.query(models.Signal)
                .filter(
                    models.Signal.source == source,
                    models.Signal.identity_key == str(identity_key),
                )
                .order_by(models.Signal.id.desc())
                .first()
            )
            if signal is None:
                raise
            if persist_evidence:
                _ensure_evidence(self.db, signal, metadata)
            return signal
        if metadata and persist_evidence:
            _ensure_evidence(self.db, signal, metadata)
        return signal

    def list_signals(
        self,
        limit: int = 100,
        min_importance: float = 0.0,
        *,
        include_user_requests: bool = True,
    ) -> list[models.Signal]:
        """Return signals at or above a minimum importance score,
        highest importance first — Forge's "most worth paying attention
        to" view."""
        query = self.db.query(models.Signal).filter(
            models.Signal.importance_score >= min_importance
        )
        if not include_user_requests:
            query = query.filter(models.Signal.source != "user_request")
        return query.order_by(
            models.Signal.importance_score.desc(),
            models.Signal.timestamp.desc(),
        ).limit(limit).all()

    def recent_signals(
        self,
        limit: int = 10,
        *,
        include_user_requests: bool = True,
    ) -> list[models.Signal]:
        """Most recently observed signals, regardless of score — the
        Dashboard's "recent discoveries" feed."""
        query = self.db.query(models.Signal)
        if not include_user_requests:
            query = query.filter(models.Signal.source != "user_request")
        return query.order_by(models.Signal.timestamp.desc()).limit(limit).all()

    def stats(self) -> dict:
        """Summary numbers for the Dashboard's Observer section."""
        total = self.db.query(models.Signal).count()
        if total == 0:
            return {
                "total_observations": 0,
                "high_importance_count": 0,
                "average_importance": 0.0,
                "low_quality_count": 0,
                "quality_flag_breakdown": {},
            }

        signals = self.db.query(
            models.Signal.importance_score, models.Signal.quality_score, models.Signal.quality_flags
        ).all()
        importance_scores = [s[0] or 0.0 for s in signals]
        high_importance_count = sum(1 for s in importance_scores if s >= 70)
        average_importance = round(sum(importance_scores) / len(importance_scores), 1)
        # quality_score is NULL for signals observed before v1.4 — only
        # count assessed ones as "low quality" rather than treating
        # "not yet assessed" as if it were disqualifying.
        low_quality_count = sum(1 for s in signals if s[1] is not None and s[1] < signal_quality.MIN_QUALITY_FOR_PATTERN)

        # v1.8: WHY signals are held below the floor, not just how many
        # — "we need to know whether Forge is rejecting good information
        # or correctly rejecting garbage." Each flag on a signal counts
        # once toward its own bucket; a signal can carry multiple flags.
        flag_breakdown: dict[str, int] = {}
        for _, _, flags in signals:
            if not flags:
                continue
            for flag in flags.split(","):
                base_flag = flag.split("_of_signal_")[0] if "duplicate_of_signal_" in flag else flag
                flag_breakdown[base_flag] = flag_breakdown.get(base_flag, 0) + 1

        signals_seed = self.db.query(models.Signal).filter(
            (models.Signal.source_type == "seed") | (models.Signal.source == "seed")
        ).count()
        signals_manual = self.db.query(models.Signal).filter(
            (models.Signal.source_type == "manual") | ((models.Signal.source == "manual") & (models.Signal.source_type.is_(None)))
        ).count()
        signals_synthetic = self.db.query(models.Signal).filter(models.Signal.source_type == "synthetic").count()
        signals_external_with_url = self.db.query(models.Signal).filter(
            models.Signal.canonical_url.isnot(None), models.Signal.canonical_url != ""
        ).count()

        opportunities_active = self.db.query(models.Opportunity).filter(models.Opportunity.status != "archived").count()
        opportunities_duplicate_archived = self.db.query(models.Opportunity).filter(models.Opportunity.status == "archived").count()

        outcomes_real = self.db.query(models.Outcome).filter(models.Outcome.data_scope == "REAL").count()
        verified_revenue = sum(
            r.revenue or 0.0
            for r in self.db.query(models.Outcome).filter(
                models.Outcome.data_scope == "REAL", models.Outcome.outcome_type == "ACTUAL_REVENUE"
            ).all()
        )

        return {
            "total_observations": total,
            "signals_total": total,
            "signals_external_with_url": signals_external_with_url,
            "signals_seed": signals_seed,
            "signals_manual": signals_manual,
            "signals_synthetic": signals_synthetic,
            "opportunities_active": opportunities_active,
            "opportunities_duplicate_archived": opportunities_duplicate_archived,
            "outcomes_real": outcomes_real,
            "verified_revenue": verified_revenue,
            "high_importance_count": high_importance_count,
            "average_importance": average_importance,
            "low_quality_count": low_quality_count,
            "quality_flag_breakdown": flag_breakdown,
        }


def _normalize_url(value: object) -> str | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return raw.rstrip("/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def _fingerprint(content: str) -> str:
    normalized = " ".join(content.split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _ensure_evidence(db: Session, signal: models.Signal, metadata: dict) -> models.Evidence:
    provenance_key = ":".join(
        part for part in (signal.source, signal.external_id, signal.canonical_url, signal.content_fingerprint) if part
    )
    provenance_hash = hashlib.sha256(provenance_key.encode("utf-8")).hexdigest()
    evidence = db.query(models.Evidence).filter(models.Evidence.provenance_hash == provenance_hash).first()
    if evidence:
        return evidence
    evidence = models.Evidence(
        signal_id=signal.id,
        source=signal.source,
        content=signal.content,
        direction="supports",
        provenance_hash=provenance_hash,
        idempotency_key=f"evidence-provenance:{provenance_hash}",
        confidence=signal.quality_score or 0.0,
        canonical_url=signal.canonical_url,
        external_id=signal.external_id,
        title=signal.title,
        published_at=signal.published_at,
        retrieved_at=signal.retrieved_at,
        content_fingerprint=signal.content_fingerprint,
        provenance=signal.provenance,
        collection_status=signal.collection_status,
    )
    try:
        with db.begin_nested():
            db.add(evidence)
            db.flush()
        db.commit()
        db.refresh(evidence)
    except IntegrityError:
        db.rollback()
        evidence = db.query(models.Evidence).filter(
            models.Evidence.idempotency_key == f"evidence-provenance:{provenance_hash}"
        ).first()
        if evidence is None:
            raise
    return evidence


# ---------------------------------------------------------------------
# Where the sources this class used to stub out actually live now:
#
#   GitHub, Reddit, News -> app/services/collectors/ (real, stdlib-only
#     implementations) + collector_runner.py (executes a ResearchTask
#     through the matching collector and calls observe() for each result)
#   Web                   -> app/services/collectors/web.py
#   Books/papers/writing    -> app/services/knowledge_miner.py
#     (extracts insight sentences from long text, calls observe() for each)
#
# Product reviews and job boards remain unimplemented — no free,
# key-less public endpoint exists for either the way there does for
# Reddit/GitHub/Google News RSS. They'd need either a paid API or a
# scraper tuned to a specific site, which is a deliberate non-goal
# ("no expensive APIs", "keep it lightweight") until a concrete source
# is chosen.
# ---------------------------------------------------------------------
