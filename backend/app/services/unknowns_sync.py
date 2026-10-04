"""Keep the production Claim store in sync with the unknowns map.

The discovery rounds bank to docs/UNKNOWN_MAP.md on main (via the local
cron's importer). Production's database doesn't see that cron, so on
startup the backend fetches the map from GitHub main and imports any new
rows. The importer dedups on normalized_statement — this is idempotent
and additive-only. Failures are logged, never fatal to startup.
"""
import logging
import urllib.request

log = logging.getLogger(__name__)

MAP_URL = (
    "https://raw.githubusercontent.com/kn33r0s3/ForgeOS/main/docs/UNKNOWN_MAP.md"
)


def sync_unknowns_from_map(db, map_url: str = MAP_URL) -> int:
    """Fetch the map, import new unknowns as Claim rows. Returns inserted."""
    from app.cli.import_unknowns import import_unknowns, parse_unknown_map

    try:
        with urllib.request.urlopen(map_url, timeout=20) as resp:
            text = resp.read().decode("utf-8")
    except Exception as exc:  # network is best-effort at startup
        log.warning("unknowns sync: could not fetch map: %s", exc)
        return 0
    try:
        unknowns = parse_unknown_map(text)
        stats = import_unknowns(unknowns, db, apply=True)
        inserted = stats.get("inserted", 0)
        if inserted:
            log.info("unknowns sync: inserted %d new claims", inserted)
        return inserted
    except Exception as exc:
        log.warning("unknowns sync: import failed: %s", exc)
        return 0
