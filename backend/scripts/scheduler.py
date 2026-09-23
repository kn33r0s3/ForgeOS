"""
SCHEDULER CLI — run ForgeOS continuously.

Usage:
    cd backend && python -m scripts.scheduler --every 3600 --backup-every 21600 --backup-keep 10

Runs the hardened daily cycle on a timer (default hourly) and writes a durable
scheduler.log trace + periodic DB snapshots to storage/backups/. Graceful on
SIGINT/SIGTERM. See app/services/cycle_scheduler.py for details.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.cycle_scheduler import run  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Run ForgeOS continuously (scheduler).")
    ap.add_argument("--every", type=int, default=3600, help="Seconds between cycle runs (default 3600).")
    ap.add_argument("--backup-every", type=int, default=6 * 3600, help="Seconds between DB backups (default 21600).")
    ap.add_argument("--backup-keep", type=int, default=10, help="Number of backups to keep (default 10).")
    args = ap.parse_args()
    run(interval=args.every, backup_every=args.backup_every, backup_keep=args.backup_keep)


if __name__ == "__main__":
    main()
