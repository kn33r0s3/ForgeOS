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

Idempotent: normalized_statement is the dedup key; re-runs only add new rows.

Usage:
    python -m app.cli.import_unknowns [--map docs/UNKNOWN_MAP.md] [--dry-run | --apply]

Defaults to --dry-run (parse only, no writes). --apply writes to the DB.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date

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

    stats = {"parsed": len(unknowns), "inserted": 0, "skipped_existing": 0}
    for u in unknowns:
        exists = (
            db.query(models.Claim)
            .filter(models.Claim.normalized_statement == u.normalized_statement)
            .first()
        )
        if exists:
            stats["skipped_existing"] += 1
            continue
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
            stats["inserted"] += 1
    if apply:
        db.commit()
    else:
        stats["inserted"] = stats["parsed"] - stats["skipped_existing"]
    return stats


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
