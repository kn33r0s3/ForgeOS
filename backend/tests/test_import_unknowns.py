"""Parser tests for the unknowns-map → primitives importer (no DB needed)."""

from pathlib import Path

from app.cli.import_unknowns import parse_unknown_map, parse_state

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
UNKNOWN_MAP = REPO_ROOT / "docs" / "UNKNOWN_MAP.md"


def read_map() -> str:
    return UNKNOWN_MAP.read_text(encoding="utf-8")


def test_state_mapping():
    assert parse_state("UNKNOWN") == "unknown"
    assert parse_state("HYPOTHESIZED") == "hypothesized"
    assert parse_state("TESTED (code, 2026-10-04): something") == "tested"
    assert parse_state("SUPPORTED (research): something") == "supported"
    assert parse_state("BLOCKED_BY_MISSING_ACCESS") == "blocked"
    assert parse_state("CONTRADICTED") == "contradicted"
    assert parse_state("SOMETHING_WEIRD") == "unknown"


def test_parses_all_sections():
    unknowns = parse_unknown_map(read_map())
    ids = [u.row_id for u in unknowns]
    # Keep the per-section inventory explicit; D rows now run through D104.
    from collections import Counter
    assert Counter(u.section for u in unknowns) == {"A": 9, "B": 4, "C": 3, "D": 104}, f"got {len(unknowns)} records"
    assert len(ids) == len(set(ids)), "row IDs must remain unique"
    assert ids[0] == "A1"
    assert "D70" in ids
    assert "D78" in ids
    assert "D96" in ids
    assert "D97" in ids
    assert "D98" in ids
    assert "D99" in ids
    assert "D100" in ids
    assert "D101" in ids
    assert "D102" in ids
    assert "D103" in ids
    assert "D104" in ids
    sections = {u.row_id: u.section for u in unknowns}
    assert sections["A1"] == "A"
    assert sections["B2"] == "B"
    assert sections["C3"] == "C"
    assert sections["D65"] == "D"


def test_provenance_and_normalization():
    unknowns = parse_unknown_map(read_map())
    d60 = next(u for u in unknowns if u.row_id == "D60")
    assert "UNKNOWN_MAP.md" in d60.provenance
    assert "D60" in d60.provenance
    assert "Cheapest test" in d60.provenance
    assert d60.normalized_statement == d60.question.strip().lower()
    assert d60.epistemic_state in ("unknown", "hypothesized", "tested", "supported", "contradicted", "blocked")


def test_no_empty_questions():
    unknowns = parse_unknown_map(read_map())
    assert all(u.question.strip() for u in unknowns)
    # normalized_statement is the idempotency key — must be unique
    keys = [u.normalized_statement for u in unknowns]
    assert len(keys) == len(set(keys)), "duplicate normalized statements would collide"
