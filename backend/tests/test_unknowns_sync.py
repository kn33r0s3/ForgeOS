"""unknowns_sync: production self-syncs the map into Claim primitives."""
from unittest.mock import patch

from app import models
from app.services.unknowns_sync import sync_unknowns_from_map


MAP_TEXT = """# Hami unknowns map

| D1 | First test question? | UNKNOWN | Ask one seller | Stakes one |
| D2 | Second test question? | UNKNOWN | Ask two sellers | Stakes two |
"""


def test_sync_imports_new_rows_idempotently(db):
    with patch("app.services.unknowns_sync.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = MAP_TEXT.encode()
        first = sync_unknowns_from_map(db)
        second = sync_unknowns_from_map(db)
    assert first == 2
    assert second == 0  # dedup: nothing new the second time
    rows = db.query(models.Claim).filter(models.Claim.provenance.like("%UNKNOWN_MAP.md%")).all()
    assert len(rows) == 2
    assert {r.epistemic_state for r in rows} == {"unknown"}


def test_sync_failure_never_raises(db):
    with patch(
        "app.services.unknowns_sync.urllib.request.urlopen",
        side_effect=Exception("network down"),
    ):
        assert sync_unknowns_from_map(db) == 0
    assert db.query(models.Claim).count() == 0
