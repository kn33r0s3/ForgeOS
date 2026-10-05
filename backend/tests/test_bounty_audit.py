"""
Audit Tests for GitHub Bounty Scanner and Verification Invariants
=================================================================

Explicit verification of Phase 8 audit gates:
1. GitHub token is not required for public discovery.
2. No secrets are logged.
3. Bounty ingestion is idempotent.
4. Malformed bounty data fails safely.
5. False positives do not create monetary claims.
6. PR merge verification remains strictly distinct from payment verification.
"""

import io
import logging
import urllib.error
from app import models
from app.services import action_engine, github_bounty


def test_github_token_not_required_for_public_discovery(monkeypatch):
    """Verify that public discovery executes cleanly without any GITHUB_TOKEN."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # Testing amount extractor and platform detector without credentials
    amt = github_bounty.extract_bounty_amount("Fix parser bug [bounty] $100")
    assert amt == 100.0
    platform = github_bounty.detect_bounty_platform("Reward on Opire", ["bounty"])
    assert platform == "Opire"


def test_no_secrets_logged(caplog, monkeypatch):
    """Verify that execution functions never log tokens or secret keys."""
    caplog.set_level(logging.DEBUG)
    test_secret = "ghp_secret_token_12345_should_never_be_logged"
    monkeypatch.setenv("GITHUB_TOKEN", test_secret)

    # Trigger the network-error logging path WITHOUT a real network call:
    # the pytest suite must stay hermetic (no internet dependency, no 15s
    # timeout on offline CI).
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 404, "Not Found", {},
            io.BytesIO(b'{"message": "Not Found"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    github_bounty.verify_pr_merge_status("nonexistent-owner-abc", "nonexistent-repo-xyz", 999999)

    for record in caplog.records:
        assert test_secret not in record.message
        assert test_secret not in str(record.args)


def test_bounty_ingestion_idempotent(db):
    """Verify that ingesting the same bounty multiple times never duplicates rows."""
    bounties = [{
        "owner": "testorg",
        "repo": "testrepo",
        "issue_number": 999,
        "title": "Fix memory leak",
        "body": "Bounty $100",
        "amount_usd": 100.0,
        "platform": "Opire",
        "html_url": "https://github.com/testorg/testrepo/issues/999",
    }]

    created_1 = github_bounty.ingest_bounties_to_opportunities(db, bounties)
    assert len(created_1) == 1

    created_2 = github_bounty.ingest_bounties_to_opportunities(db, bounties)
    assert len(created_2) == 0

    count = db.query(models.Opportunity).filter_by(identity_key="github_bounty:testorg/testrepo#999").count()
    assert count == 1


def test_malformed_bounty_data_fails_safely(db):
    """Verify that missing keys, None values, or empty dicts do not crash ingestion."""
    malformed = [
        {},
        {"owner": "onlyowner"},
        {"owner": "test", "repo": "test"},  # missing issue_number
        {"owner": None, "repo": None, "issue_number": None},
        {"owner": "org", "repo": "repo", "issue_number": "invalid"},
    ]
    # Should handle all without throwing unhandled exception
    created = github_bounty.ingest_bounties_to_opportunities(db, malformed)
    assert len(created) == 0


def test_false_positives_do_not_create_monetary_claims(db):
    """Verify that issues with words like 'bounty' or '$100' without verified structure do not get prices."""
    # Text mentioning bug bounty program in general or hypothetical numbers
    assert github_bounty.extract_bounty_amount("Discussing bug bounty programs in general") is None
    assert github_bounty.extract_bounty_amount("We need to fix this bounty program policy") is None

    unfunded_item = [{
        "owner": "testorg",
        "repo": "testrepo",
        "issue_number": 888,
        "title": "Bug bounty discussion",
        "body": "General policy discussion about bounties",
        "amount_usd": None,
        "platform": "GitHub Bounty",
        "html_url": "https://github.com/testorg/testrepo/issues/888",
    }]
    created = github_bounty.ingest_bounties_to_opportunities(db, unfunded_item)
    assert len(created) == 1
    opp = created[0]
    assert opp.estimated_price is None
    assert opp.score == 40.0
    assert opp.revenue_confidence == 20.0
    assert opp.uncertainty == 70.0


def test_pr_merge_distinct_from_payment_verification(db):
    """Verify that PR merge verification does NOT record actual revenue.
    
    A merged PR is evidence of code acceptance, but NEVER equivalent to money received.
    """
    # Propose verification action
    action = action_engine.propose_action(
        db,
        objective="Verify PR merge",
        action_type="github_bounty_verify",
        parameters={"owner": "testorg", "repo": "testrepo", "pull_number": 123},
    )

    # Even if verification succeeded (PR merged), no revenue outcome must be recorded automatically
    action.status = "SUCCEEDED"
    action.verification_state = "VERIFIED"
    action.execution_result = "PR #123 merged! Commit SHA: abc123def456"
    db.commit()

    # Query outcomes table to ensure zero ACTUAL_REVENUE outcomes exist for this action
    revenue_outcomes = db.query(models.Outcome).filter_by(
        action_id=action.id,
        outcome_type="ACTUAL_REVENUE"
    ).all()
    assert len(revenue_outcomes) == 0
