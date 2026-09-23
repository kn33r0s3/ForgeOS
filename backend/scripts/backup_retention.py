"""Archive legacy root-level SQLite snapshots and prune old compressed backups.

Safe by default: dry-run only. Use --apply after reviewing the printed plan.
The live storage/forge.db file is never selected.
"""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "storage"
LEGACY_ARCHIVE = STORAGE / "backups" / "legacy"


def plan_legacy(keep: int) -> tuple[list[Path], list[Path]]:
    candidates = sorted(
        STORAGE.glob("forgeos_pre_*.db"), key=lambda path: path.stat().st_mtime_ns, reverse=True
    )
    return candidates[:keep], candidates[keep:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the ForgeOS backup retention policy.")
    parser.add_argument("--keep-legacy", type=int, default=2, help="Recent legacy .db snapshots to leave in storage/.")
    parser.add_argument("--keep-compressed", type=int, default=10, help="Recent storage/backups/forge_*.db.gz files to retain.")
    parser.add_argument("--apply", action="store_true", help="Perform moves/deletions. Without this flag, print a dry run.")
    args = parser.parse_args()
    if args.keep_legacy < 1 or args.keep_compressed < 1:
        raise SystemExit("retention values must be >= 1")

    kept, to_archive = plan_legacy(args.keep_legacy)
    compressed = sorted((STORAGE / "backups").glob("forge_*.db.gz"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    to_prune = compressed[args.keep_compressed:]
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"[{mode}] live database preserved: {STORAGE / 'forge.db'}")
    print("legacy snapshots kept in storage:", *(p.name for p in kept), sep="\n  ")
    print("legacy snapshots to archive:", *(p.name for p in to_archive), sep="\n  ")
    print("compressed snapshots to prune:", *(p.name for p in to_prune), sep="\n  ")
    if not args.apply:
        return

    LEGACY_ARCHIVE.mkdir(parents=True, exist_ok=True)
    for path in to_archive:
        destination = LEGACY_ARCHIVE / path.name
        if destination.exists():
            path.unlink(missing_ok=True)
        else:
            shutil.move(str(path), destination)
        checksum = path.with_suffix(".sha256")
        if checksum.exists():
            checksum_destination = LEGACY_ARCHIVE / checksum.name
            if checksum_destination.exists():
                checksum.unlink(missing_ok=True)
            else:
                shutil.move(str(checksum), checksum_destination)
    for path in to_prune:
        path.unlink(missing_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"retention applied at {stamp}")


if __name__ == "__main__":
    main()
