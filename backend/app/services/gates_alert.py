"""Gates alert — run the daily gate check and alert the owner on red.

Step 7 of the gates order. Runs the bypass tests and generates GATES.md. On
red, it uses the owner-control outbox/dispatcher path to send a Telegram alert.
On green it does nothing.

If the Telegram owner channel is not configured, it does not fake a send:
it returns blocked_by="BLOCKED_BY_MISSING_ACCESS". `notified` means the
dispatcher persisted a SUCCEEDED outbox row after Telegram API acceptance; it
does not establish that the owner saw the message.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import date
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session

from app import models
from app.services import owner_control

logger = logging.getLogger(__name__)

BLOCKED_BY_MISSING_ACCESS = "BLOCKED_BY_MISSING_ACCESS"


def _run_gates_check(repo_root: Path) -> tuple[bool, list[str]]:
    """Run the gates tests + the report. Returns (green, red_reasons)."""
    reasons: list[str] = []
    # 1. The bypass tests.
    test = subprocess.run(
        ["node", "--experimental-strip-types", "--test", "src/lib/gates.test.ts"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    combined = (test.stdout or "") + (test.stderr or "")
    if test.returncode != 0 or "fail 0" not in combined:
        reasons.append("gates tests failing (see src/lib/gates.test.ts)")
    # 2. The generated report.
    report = subprocess.run(
        ["node", "scripts/gates-report.mjs"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if report.returncode != 0 or " — RED" in (report.stdout or ""):
        reasons.append("gates:report says RED — a gate is open or bypassed")
    return (len(reasons) == 0, reasons)


def _telegram_configured() -> bool:
    """True only when the Telegram owner channel can actually send."""
    return owner_control.control_ready()


def run_gates_alert(db: Session, repo_root: Path | str) -> dict[str, Any]:
    """Run the daily gates check. Silent on green; Telegram alert on red.

    Returns a dict with status ("green" | "red"), notified (bool), reasons
    (list), delivery evidence when available, and blocked_by when delivery is
    unavailable. Never treats enqueueing as notification.
    """
    root = Path(repo_root)
    green, reasons = _run_gates_check(root)
    if green:
        logger.info("gates alert: GREEN — silent")
        return {"status": "green", "notified": False, "reasons": []}
    message = (
        "Hami gates RED — a gate is open or bypassed:\n"
        + "\n".join(f"- {r}" for r in reasons)
        + "\nSee docs/GATES.md."
    )
    if not _telegram_configured():
        logger.warning(
            "gates alert: RED but Telegram channel not configured — %s",
            BLOCKED_BY_MISSING_ACCESS,
        )
        return {
            "status": "red",
            "notified": False,
            "blocked_by": BLOCKED_BY_MISSING_ACCESS,
            "reasons": reasons,
        }
    delivery_result = owner_control.enqueue_owner_message(
        db,
        key=f"gates-alert-{date.today().isoformat()}",
        body=message,
        kind="alert",
    )
    delivery_id = delivery_result.get("delivery_id")
    delivery = (
        db.get(models.IntegrationDelivery, delivery_id)
        if type(delivery_id) is int
        else None
    )
    notified = (
        delivery_result.get("status") == "provider_accepted"
        and delivery is not None
        and delivery.status == "SUCCEEDED"
    )
    delivery_status = delivery.status if delivery is not None else delivery_result.get("status")
    if notified:
        logger.warning("gates alert: RED — Telegram API accepted alert (delivery %s)", delivery_id)
    else:
        logger.warning(
            "gates alert: RED — Telegram delivery blocked (delivery %s, status %s)",
            delivery_id,
            delivery_status,
        )
    result = {
        "status": "red",
        "notified": notified,
        "delivery_id": delivery_id,
        "delivery_status": delivery_status,
        "reasons": reasons,
    }
    if "delivery_claim" in delivery_result:
        result["delivery_claim"] = delivery_result["delivery_claim"]
    if not notified:
        result["blocked_by"] = BLOCKED_BY_MISSING_ACCESS
    return result
