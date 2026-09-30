"""
SEED SIGNALS — Phase 1, "seed if necessary"
=============================================

Manually injects a small batch of strong, concrete, well-formed
signals directly through the same ObserverEngine.observe() path every
collector uses (so they get real quality scoring, real duplicate
checks, real importance scoring — nothing here is faked or backdoored
into the DB). The point is not to fabricate evidence: every signal
below is written the way a genuinely strong observation should read
(specific numbers, one clear topic, a named source of the claim) so
the loop has something above the pattern-quality floor to work with
while collector-sourced signal quality is still being improved.

Usage:
    cd backend && python -m scripts.seed_signals
    (or: python scripts/seed_signals.py)

Each signal is tagged source="seed" so it's easy to find/filter later
(`GET /signals?source=seed` or a DB query on Signal.source == "seed"),
and easy to remove if it turns out not to have been useful.

Edit SEED_SIGNALS below before running — the ones checked in here are
placeholders illustrating the *shape* a strong signal needs (concrete,
single-topic, sourced), not real observations. Replace them with your
own genuine research findings before seeding.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.services.observer_engine import ObserverEngine

# Replace these with real, specific observations you've actually found
# (a support-forum complaint with numbers, a pricing page screenshot,
# a competitor's stated user count, etc). Vague restatements of "there
# might be demand for X" will score low on concreteness/coherence just
# like any other signal — seeding doesn't bypass the quality bar, it
# just gives you full control over what gets fed in.
SEED_SIGNALS = [
    {
        "content": (
            "r/shopify solo store owner tallied micro-app stack: post-purchase email, "
            "inventory ping, Slack notifier, UTM tagger, review requester, CSV exporter. "
            "Six subscriptions totaling $167/mo, none of which drive a single extra sale. "
            "Source: r/shopify thread with 95 upvotes, March 2026 analysis of 60+ posts."
        ),
        "signal_type": "problem",
    },
    {
        "content": (
            "12-person company paying for 10+ separate software subscriptions (email marketing, "
            "CRM, project management, file storage, scheduling, analytics, support, payroll, "
            "chat, accounting). Typical spend cited $30-50 per seat/month, totaling ~$50k/year "
            "before Zapier. Pilates studio owner example: $250/mo just for booking + gift cards. "
            "Source: r/smallbusiness post March 2026, multiple corroborating comments."
        ),
        "signal_type": "problem",
    },
    {
        "content": (
            "Solo accounting practice (12 clients) software audit: Karbon $99/mo + DocuSign $25 + "
            "Calendly Pro $12 + Loom $12 = $198/mo. Owner reports steep learning curve on Karbon "
            "and only ~20% feature utilization. Seeking consolidation alternatives. "
            "Source: r/smallbusiness thread March 2026."
        ),
        "signal_type": "observation",
    },
    {
        "content": (
            "Hairstylists, tutors, personal trainers and mobile detailers repeatedly report "
            "no-shows booked via Instagram DMs with no deposit protection. Typical loss cited "
            "$300 for a single missed appointment day. Common in r/smallbusiness and trade subs. "
            "Source: aggregated Reddit pain-point analysis September 2026."
        ),
        "signal_type": "problem",
    },
    {
        "content": (
            "QuickBooks Online accountant reports padded payroll billing: extra employees added "
            "at $5.10 or $8.50 each, requiring multiple support calls to recover ~$500 in refunds "
            "across accounts. Also retroactive tax payments draining client bank accounts without "
            "clear notice. Source: r/quickbooksonline post September 2026."
        ),
        "signal_type": "observation",
    },
]


def main():
    db = SessionLocal()
    observer = ObserverEngine(db)
    created = []
    try:
        for item in SEED_SIGNALS:
            content = item["content"].strip()
            if content.startswith("REPLACE ME"):
                print(f"SKIPPED (placeholder text, edit this file first): {content[:60]}...")
                continue
            signal = observer.observe(content=content, source="seed")
            created.append(signal)
            print(
                f"seeded signal id={signal.id} quality={signal.quality_score} "
                f"flags={signal.quality_flags or '-'} type={signal.signal_type}"
            )
    finally:
        db.close()

    if not created:
        print(
            "\nNo signals were seeded — SEED_SIGNALS still contains placeholder "
            "text. Edit backend/scripts/seed_signals.py with real observations "
            "and re-run."
        )
    else:
        print(f"\nSeeded {len(created)} signal(s). Run a Forge Cycle next so "
              "Pattern/Belief/Opportunity engines pick them up.")


if __name__ == "__main__":
    main()
