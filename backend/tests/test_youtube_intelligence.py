import json

import pytest

from app import models
from app.services import youtube_intelligence
from app.services.tool_registry import default_registry


VIDEO_URL = "https://www.youtube.com/watch?v=abc123XYZ_1"


def fake_fetch(url):
    if "oembed" in url:
        return json.dumps({"title": "Repair systems", "author_name": "Test Channel", "thumbnail_url": "https://img.test/thumb"}).encode()
    return b'<transcript><text start="0.0" dur="2.0">Contractors lose hours manually scheduling repairs.</text><text start="2.0" dur="3.0">They currently use spreadsheets and phone calls.</text></transcript>'


def unavailable_fetch(url):
    if "oembed" in url:
        return json.dumps({"title": "No transcript video", "author_name": "Channel"}).encode()
    raise RuntimeError("timed text unavailable")


def test_valid_url_and_metadata():
    assert youtube_intelligence.video_id_from_url(VIDEO_URL) == "abc123XYZ_1"
    metadata = youtube_intelligence.fetch_metadata("abc123XYZ_1", fetch=fake_fetch)
    assert metadata["title"] == "Repair systems"
    assert metadata["channel"] == "Test Channel"
    assert youtube_intelligence.canonical_url("abc123XYZ_1") == VIDEO_URL


def test_invalid_url_and_missing_transcript_are_honest(db):
    with pytest.raises(ValueError):
        youtube_intelligence.video_id_from_url("https://example.com/video")

    result = youtube_intelligence.analyze_youtube(db, VIDEO_URL, fetch=unavailable_fetch)
    analysis = result["analysis"]
    assert analysis.status == "transcript_unavailable"
    assert analysis.error == "timed text unavailable"
    assert analysis.title == "No transcript video"
    assert analysis.duration_seconds is None
    assert analysis.published_at is None
    assert result["claims"] == []


def test_optional_local_transcription_fallback_is_preserved(db):
    result = youtube_intelligence.analyze_youtube(
        db,
        VIDEO_URL,
        fetch=unavailable_fetch,
        transcribe_fallback=lambda url: {
            "available": True,
            "source": "local-whisper-test",
            "language": "en",
            "segments": [{"text": "Contractors report a recurring scheduling problem.", "start_seconds": 4.0}],
        },
    )

    assert result["analysis"].status == "extracted"
    assert result["analysis"].transcript_source == "local-whisper-test"
    assert result["analysis"].transcript_segments[0]["start_seconds"] == 4.0
    assert result["claims"]


def test_transcript_timestamps_claims_provenance_and_reuse(db):
    first = youtube_intelligence.analyze_youtube(db, VIDEO_URL, fetch=fake_fetch)
    analysis = first["analysis"]

    assert analysis.status == "extracted"
    assert analysis.transcript_source == "youtube_timedtext"
    assert analysis.transcript_segments[0]["start_seconds"] == 0.0
    assert analysis.transcript_segments[1]["start_seconds"] == 2.0
    assert len(first["claims"]) == 2
    assert all(claim.epistemic_state == "observed" for claim in first["claims"])
    assert all(claim.confidence is None for claim in first["claims"])
    assert db.query(models.WorldSourceDocument).count() == 1
    assert db.query(models.Evidence).count() == 2
    assert db.query(models.EvidenceRelationship).count() == 2
    assert db.query(models.ResearchQuestion).count() == 2

    second = youtube_intelligence.analyze_youtube(db, "https://youtu.be/abc123XYZ_1", fetch=fake_fetch)
    assert second["reused"] is True
    assert second["analysis"].id == analysis.id
    assert db.query(models.MediaAnalysis).count() == 1
    assert db.query(models.Claim).count() == 2
    assert db.query(models.Evidence).count() == 2


def test_youtube_tool_is_registered_without_making_ai_or_audio_claims():
    registry = default_registry()
    tool = registry.get("youtube-intelligence")
    assert tool.is_available() is True
    assert "transcript" in tool.capability.capabilities
    assert "audio_transcription" not in tool.capability.capabilities
