"""Provider-neutral YouTube/media intelligence adapter.

Acquisition is deliberately best-effort and honest: public oEmbed metadata and
YouTube timed-text transcripts are used when available; missing fields remain
null and failures are persisted rather than fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import re
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from sqlalchemy.orm import Session

from app import models
from app.services import evidence_graph, research_planner, intelligence_cache
from app.services.tool_registry import ToolCapability

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")


@dataclass
class MediaResult:
    analysis: models.MediaAnalysis
    reused: bool


def utcnow():
    return datetime.now(timezone.utc)


def video_id_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in YOUTUBE_HOSTS:
        raise ValueError("expected a YouTube URL")
    if parsed.netloc.lower() == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    else:
        candidate = parse_qs(parsed.query).get("v", [""])[0]
        if not candidate and parsed.path.startswith("/shorts/"):
            candidate = parsed.path.split("/", 2)[2].split("/", 1)[0]
        if not candidate and parsed.path.startswith("/embed/"):
            candidate = parsed.path.split("/", 2)[2].split("/", 1)[0]
    if not VIDEO_ID_RE.match(candidate):
        raise ValueError("YouTube video ID not found")
    return candidate


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _request_json(url: str, fetch: Callable[[str], bytes] | None = None) -> dict[str, Any]:
    if fetch:
        return json.loads(fetch(url).decode("utf-8"))
    request = Request(url, headers={"User-Agent": "ForgeOS/1.0 media intelligence"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_metadata(video_id: str, fetch: Callable[[str], bytes] | None = None) -> dict[str, Any]:
    data = _request_json(f"https://www.youtube.com/oembed?url={quote(canonical_url(video_id))}&format=json", fetch)
    return {
        "title": data.get("title"),
        "channel": data.get("author_name"),
        "thumbnail_url": data.get("thumbnail_url"),
        "source": "youtube_oembed",
    }


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def fetch_transcript(video_id: str, fetch: Callable[[str], bytes] | None = None) -> dict[str, Any]:
    """Fetch public timed-text XML; absence is a real unavailable result."""
    url = f"https://www.youtube.com/api/timedtext?lang=en&v={quote(video_id)}"
    try:
        raw = fetch(url) if fetch else urlopen(Request(url, headers={"User-Agent": "ForgeOS/1.0"}), timeout=15).read()
        root = ET.fromstring(raw)
    except Exception as exc:
        return {"available": False, "source": "youtube_timedtext", "error": str(exc), "segments": []}
    segments = []
    for node in root.findall(".//text"):
        text = _clean_text("".join(node.itertext()))
        if not text:
            continue
        start = node.attrib.get("start")
        duration = node.attrib.get("dur")
        segments.append({"text": text, "start_seconds": float(start) if start else None, "duration_seconds": float(duration) if duration else None})
    if not segments:
        return {"available": False, "source": "youtube_timedtext", "error": "transcript unavailable", "segments": []}
    return {"available": True, "source": "youtube_timedtext", "language": "en", "segments": segments}


def _hash_text(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def _ensure_task_for_claim(db: Session, claim: models.Claim) -> None:
    question = f"Verify this media claim independently: {claim.statement}"
    existing = db.query(models.ResearchQuestion).filter_by(question=question).first()
    if existing:
        return
    row = models.ResearchQuestion(
        question=question,
        priority_score=75.0,
        status="open",
        source_claim_id=claim.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    research_planner.plan_tasks_for_question(db, row)


def extract_claims(db: Session, analysis: models.MediaAnalysis) -> list[models.Claim]:
    if not analysis.transcript_text or not analysis.document_id:
        return []
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", analysis.transcript_text) if len(part.strip()) >= 30]
    claims: list[models.Claim] = []
    for sentence in sentences[:30]:
        # This is extraction only. It never assigns truth or confidence.
        claim, _ = evidence_graph.create_or_get_claim(
            db,
            sentence,
            epistemic_state="observed",
            provenance={"media_analysis_id": analysis.id, "document_id": analysis.document_id, "method": "transcript_sentence_v1"},
        )
        evidence_hash = hashlib.sha256(f"media:{analysis.external_id}:{_hash_text(sentence)}".encode()).hexdigest()
        evidence, _ = evidence_graph.get_or_create_evidence(
            db,
            provenance_hash=evidence_hash,
            source="youtube",
            content=sentence,
            title=analysis.title,
            canonical_url=analysis.source_uri,
            external_id=analysis.external_id,
            provenance={"media_analysis_id": analysis.id, "extraction_method": "transcript_sentence_v1"},
            collection_status="extracted",
        )
        evidence_graph.link_evidence(db, evidence, claim=claim, relation_type="derived_from")
        _ensure_task_for_claim(db, claim)
        claims.append(claim)
    return claims


class YouTubeIntelligenceTool:
    capability = ToolCapability(
        name="youtube-intelligence",
        category="media",
        input_types=("youtube_url",),
        output_types=("metadata", "transcript", "claims", "evidence"),
        cost="free",
        latency="network",
        reliability=0.5,
        languages=("en",),
        media_support=("video", "audio", "text"),
        availability="optional_public_source",
        capabilities=("metadata", "transcript", "timestamps", "claim_extraction"),
    )

    def is_available(self) -> bool:
        return True

    def execute(self, url: str, **kwargs: Any) -> dict[str, Any]:
        return analyze_youtube(kwargs["db"], url, fetch=kwargs.get("fetch"))


def analyze_youtube(
    db: Session,
    url: str,
    *,
    fetch: Callable[[str], bytes] | None = None,
    transcribe_fallback: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    video_id = video_id_from_url(url)
    source_uri = canonical_url(video_id)
    existing = db.query(models.MediaAnalysis).filter_by(external_id=video_id).first()
    if existing and existing.content_hash:
        return {"analysis": existing, "claims": [], "reused": True}
    if not existing:
        existing = models.MediaAnalysis(source_uri=source_uri, external_id=video_id, status="processing")
        db.add(existing)
        db.commit()
        db.refresh(existing)
    try:
        metadata_entry, metadata_hit = intelligence_cache.get(
            db, object_type="youtube_metadata", value=video_id
        )
        if metadata_hit and metadata_entry:
            metadata = json.loads(metadata_entry.content)
        else:
            metadata = fetch_metadata(video_id, fetch=fetch)
            intelligence_cache.put(
                db, object_type="youtube_metadata", value=video_id,
                content=json.dumps(metadata, sort_keys=True), metadata={"source": "youtube_oembed"},
            )
        transcript_entry, transcript_hit = intelligence_cache.get(
            db, object_type="youtube_transcript", value=video_id
        )
        if transcript_hit and transcript_entry:
            transcript = json.loads(transcript_entry.content)
        else:
            transcript = fetch_transcript(video_id, fetch=fetch)
            if transcript.get("available"):
                intelligence_cache.put(
                    db, object_type="youtube_transcript", value=video_id,
                    content=json.dumps(transcript, sort_keys=True), metadata={"source": transcript.get("source")},
                )
        if not transcript.get("available") and transcribe_fallback is not None:
            fallback_result = transcribe_fallback(source_uri)
            if fallback_result.get("available"):
                transcript = {
                    **fallback_result,
                    "source": fallback_result.get("source", "local_transcription"),
                }
        existing.title = metadata.get("title")
        existing.channel = metadata.get("channel")
        existing.metadata_json = metadata
        existing.transcript_source = transcript.get("source")
        existing.transcript_segments = transcript.get("segments")
        existing.language = transcript.get("language")
        existing.extraction_method = "youtube_timedtext + transcript_sentence_v1"
        if not transcript.get("available"):
            existing.status = "transcript_unavailable"
            existing.error = transcript.get("error")
            db.commit()
            return {"analysis": existing, "claims": [], "reused": False}
        existing.transcript_text = " ".join(segment["text"] for segment in transcript["segments"])
        existing.content_hash = _hash_text(existing.transcript_text)
        document = db.query(models.WorldSourceDocument).filter_by(content_hash=existing.content_hash).first()
        if not document:
            document = models.WorldSourceDocument(
                source_uri=source_uri,
                source_type="youtube_transcript",
                language_original=existing.language,
                title=existing.title,
                content_text=existing.transcript_text,
                content_hash=existing.content_hash,
                access_basis="public_page",
                retrieved_at=utcnow(),
            )
            db.add(document)
            db.commit()
            db.refresh(document)
        existing.document_id = document.id
        existing.status = "extracted"
        existing.error = None
        existing.updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        claims = extract_claims(db, existing)
        return {"analysis": existing, "claims": claims, "reused": False}
    except Exception as exc:
        existing.status = "failed"
        existing.error = str(exc)
        existing.updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        return {"analysis": existing, "claims": [], "reused": False}
