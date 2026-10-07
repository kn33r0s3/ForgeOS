"""
Tests for GitHub Bounty Adapter and Action Integration
======================================================
"""

import json
from unittest.mock import patch

import pytest
from app import models
from app.services import action_engine, github_bounty


def test_extract_bounty_amount():
    assert github_bounty.extract_bounty_amount("Fix login bug [bounty] $150") == 150.0
    assert github_bounty.extract_bounty_amount("Issue with /bounty 50.00") == 50.0
    assert github_bounty.extract_bounty_amount("@opire-dev create $250") == 250.0
    assert github_bounty.extract_bounty_amount("Bounty: $75 on completion") == 75.0
    # Thousands separators must not truncate the amount ("$5,000" was parsed as 5.0)
    assert github_bounty.extract_bounty_amount("$5,000 bounty") == 5000.0
    assert github_bounty.extract_bounty_amount("bounty: $12,500.00 for the fix") == 12500.0
    assert github_bounty.extract_bounty_amount("Regular issue without reward") is None


def test_detect_bounty_platform():
    assert github_bounty.detect_bounty_platform("Using @opire-dev create $50", []) == "Opire"
    assert github_bounty.detect_bounty_platform("Funded via algora.io/bounties", []) == "Algora"
    assert github_bounty.detect_bounty_platform("Issue with polar.sh", ["bounty"]) == "Polar"
    assert github_bounty.detect_bounty_platform("Custom bounty", ["bounty"]) == "GitHub Bounty"


def test_ingest_bounties_to_opportunities_idempotent(db):
    bounties = [
        {
            "issue_id": 101,
            "issue_number": 42,
            "title": "Fix memory leak in parser",
            "body": "There is a memory leak. Bounty: $100.",
            "html_url": "https://github.com/testorg/testrepo/issues/42",
            "owner": "testorg",
            "repo": "testrepo",
            "labels": ["bounty", "bug"],
            "amount_usd": 100.0,
            "platform": "Algora",
            "claim_command": "/attempt",
        }
    ]

    # First ingestion
    created = github_bounty.ingest_bounties_to_opportunities(db, bounties)
    assert len(created) == 1
    opp = created[0]
    assert opp.identity_key == "github_bounty:testorg/testrepo#42"
    assert opp.estimated_price == 100.0
    assert opp.monetization_model == "bounty"
    assert opp.target_customer == "testorg/testrepo"

    # Second ingestion with same data (idempotency check)
    created_again = github_bounty.ingest_bounties_to_opportunities(db, bounties)
    assert len(created_again) == 0

    total = db.query(models.Opportunity).filter_by(identity_key="github_bounty:testorg/testrepo#42").count()
    assert total == 1


def test_claim_bounty_fails_closed_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GITHUB_TOKEN is not configured"):
        github_bounty.post_bounty_claim_comment(
            owner="testorg",
            repo="testrepo",
            issue_number=42,
            github_token="",
        )


def test_verify_pr_merge_status_merged():
    mock_response = {
        "merged": True,
        "merged_at": "2026-09-22T20:00:00Z",
        "merge_commit_sha": "abc123def456",
        "html_url": "https://github.com/testorg/testrepo/pull/1",
        "state": "closed",
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode("utf-8")
        res = github_bounty.verify_pr_merge_status(owner="testorg", repo="testrepo", pull_number=1)
        assert res["verified"] is True
        assert res["merged"] is True
        assert res["merge_commit_sha"] == "abc123def456"


def test_verify_pr_merge_status_open():
    mock_response = {
        "merged": False,
        "merged_at": None,
        "state": "open",
        "html_url": "https://github.com/testorg/testrepo/pull/2",
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_response).encode("utf-8")
        res = github_bounty.verify_pr_merge_status(owner="testorg", repo="testrepo", pull_number=2)
        assert res["verified"] is False
        assert res["merged"] is False
        assert res["status"] == "OPEN"


def test_action_engine_github_bounty_claim_fails_closed_without_token(db, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    action = action_engine.propose_action(
        db,
        objective="Claim bounty on issue #42",
        action_type="github_bounty_claim",
        parameters={"owner": "testorg", "repo": "testrepo", "issue_number": 42},
    )

    executed = action_engine.start_and_execute_action(db, action.id)
    assert executed.status == "FAILED"
    assert "GITHUB_TOKEN is not configured" in executed.execution_error
    assert executed.verification_state == "CREDENTIALS_REQUIRED"


def test_action_engine_github_bounty_verify(db):
    action = action_engine.propose_action(
        db,
        objective="Verify PR merge for bounty",
        action_type="github_bounty_verify",
        parameters={"owner": "testorg", "repo": "testrepo", "pull_number": 99},
    )

    mock_merged = {
        "merged": True,
        "merged_at": "2026-09-22T21:00:00Z",
        "merge_commit_sha": "sha789",
        "html_url": "https://github.com/testorg/testrepo/pull/99",
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_merged).encode("utf-8")
        executed = action_engine.start_and_execute_action(db, action.id)
        assert executed.status == "SUCCEEDED"
        assert executed.verification_state == "VERIFIED"
        assert "sha789" in executed.execution_result
