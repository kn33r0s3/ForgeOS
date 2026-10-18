"""
UNKNOWN MAP → PRIMITIVES IMPORTER
=================================
The start of Hami as a living system: the knowledge base (docs/UNKNOWN_MAP.md)
moves INTO the six primitives as the system of record, instead of living only
in markdown files disconnected from them.

Parses the unknowns map and creates Claim rows (one per unknown):
  statement        = the unknown question
  epistemic_state  = normalized from the State column
  provenance       = map section + row id + cheapest test
  confidence       = 0.0 (unmeasured until tested — never inflated)

Idempotent: the map row id (D72, B1, …) is the dedup key. Re-runs skip
rows whose text is unchanged; when a discovery round revises a row's
wording, the newest stored row is updated in place and older revisions
of the same row id are retired (never ones other records point at).

Usage:
    python -m app.cli.import_unknowns [--map docs/UNKNOWN_MAP.md] [--dry-run | --apply]

Defaults to --dry-run (parse only, no writes). --apply writes to the DB.
"""

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date

log = logging.getLogger(__name__)

STATE_MAP = {
    "UNKNOWN": "unknown",
    "HYPOTHESIZED": "hypothesized",
    "TESTED": "tested",
    "SUPPORTED": "supported",
    "CONTRADICTED": "contradicted",
    "BLOCKED_BY_MISSING_ACCESS": "blocked",
}

ROW_RE = re.compile(r"^\|\s*([A-Z]+\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$")


@dataclass
class ParsedUnknown:
    row_id: str
    section: str
    question: str
    state_raw: str
    epistemic_state: str
    cheapest_test: str
    stakes: str

    @property
    def normalized_statement(self) -> str:
        return re.sub(r"\s+", " ", self.question.strip().lower())

    @property
    def provenance(self) -> str:
        # Stamped with the import run date, not a hardcoded one: a stale
        # hardcoded date would claim every future import happened on
        # 2026-10-04.
        return (
            f"UNKNOWN_MAP.md §{self.section} row {self.row_id} "
            f"(imported {date.today().isoformat()}). Cheapest test: {self.cheapest_test}"
        )


def parse_state(raw: str) -> str:
    """'TESTED (code, 2026-10-04): ...' -> 'tested'. Unknown tokens -> 'unknown'."""
    token = re.split(r"[\s(]", raw.strip(), maxsplit=1)[0].upper()
    return STATE_MAP.get(token, "unknown")


def parse_unknown_map(text: str) -> list[ParsedUnknown]:
    section = "?"
    out: list[ParsedUnknown] = []
    for line in text.splitlines():
        m = re.match(r"^## ([A-D])\.", line)
        if m:
            section = m.group(1)
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        row_id, question, state_raw, cheapest_test, stakes = m.groups()
        if row_id.startswith("D") and not question:
            continue
        out.append(
            ParsedUnknown(
                row_id=row_id,
                section=section,
                question=question,
                state_raw=state_raw,
                epistemic_state=parse_state(state_raw),
                cheapest_test=cheapest_test,
                stakes=stakes,
            )
        )
    return out


def import_unknowns(unknowns: list[ParsedUnknown], db, apply: bool = False) -> dict:
    from app import models

    stats = {
        "parsed": len(unknowns),
        "inserted": 0,
        "skipped_existing": 0,
        "updated": 0,
        "retired_dupes": 0,
    }
    for u in unknowns:
        # Stable identity is the map row id; the question text is mutable
        # (discovery rounds revise wording). A text-only dedup key reinserts
        # a new row on every revision and never retires the old one.
        # The trailing space keeps "row D7" from matching "row D72".
        existing = (
            db.query(models.Claim)
            .filter(models.Claim.provenance.like(f"%row {u.row_id} %"))
            .order_by(models.Claim.id)
            .all()
        )
        current = next(
            (e for e in existing if e.normalized_statement == u.normalized_statement),
            None,
        )
        if current is not None:
            stats["skipped_existing"] += 1
            if apply:
                stats["retired_dupes"] += _retire_older_dupes(
                    db, models, [e for e in existing if e.id != current.id]
                )
            continue
        # Safety net: text already stored under a provenance without a row id.
        text_match = (
            db.query(models.Claim)
            .filter(models.Claim.normalized_statement == u.normalized_statement)
            .first()
        )
        if text_match is not None:
            stats["skipped_existing"] += 1
            continue
        if existing:
            # Map row revised since last import: update the newest stored
            # row in place so the Claim id stays stable, retire older ones.
            stats["updated"] += 1
            if apply:
                newest = existing[-1]
                newest.statement = u.question
                newest.normalized_statement = u.normalized_statement
                newest.epistemic_state = u.epistemic_state
                newest.provenance = u.provenance
                stats["retired_dupes"] += _retire_older_dupes(db, models, existing[:-1])
            continue
        stats["inserted"] += 1
        if apply:
            db.add(
                models.Claim(
                    statement=u.question,
                    normalized_statement=u.normalized_statement,
                    epistemic_state=u.epistemic_state,
                    confidence=0.0,
                    provenance=u.provenance,
                )
            )
    if apply:
        db.commit()
    return stats


def _retire_older_dupes(db, models, dupes: list) -> int:
    """Delete superseded duplicate rows — never ones other records point at."""
    retired = 0
    for d in dupes:
        linked = (
            db.query(models.EvidenceRelationship).filter_by(claim_id=d.id).first() is not None
            or db.query(models.Judgment).filter_by(claim_id=d.id).first() is not None
        )
        if linked:
            log.info("unknowns import: keeping duplicate claim %s (has linked records)", d.id)
            continue
        db.delete(d)
        retired += 1
    return retired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import UNKNOWN_MAP.md into Claim primitives")
    parser.add_argument("--map", default="docs/UNKNOWN_MAP.md")
    parser.add_argument("--apply", action="store_true", help="write to the DB (default: dry run)")
    args = parser.parse_args(argv)

    with open(args.map, encoding="utf-8") as f:
        unknowns = parse_unknown_map(f.read())

    from app.database import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        stats = import_unknowns(unknowns, db, apply=args.apply)
    finally:
        db.close()

    print(f"parsed={stats['parsed']} inserted={stats['inserted']} "
          f"skipped_existing={stats['skipped_existing']} apply={args.apply}")
    by_state: dict[str, int] = {}
    for u in unknowns:
        by_state[u.epistemic_state] = by_state.get(u.epistemic_state, 0) + 1
    print("by_state=" + ", ".join(f"{k}={v}" for k, v in sorted(by_state.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
