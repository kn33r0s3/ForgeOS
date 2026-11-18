"""
ACTION ENGINE
==============

Separates DECISION from ACTION from OUTCOME.

- Decision: why we chose a path
- Action: unit of work (may succeed at execution without producing business outcome)
- Outcome: measured reality after the fact (ACTUAL only)

Adapters execute actions. Unsupported external actions return UNSUPPORTED
rather than fabricating success.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services import autonomy_engine, decision_rights
from app.services.execution_boundary import Action as BoundaryAction
from app.services.execution_boundary import Operation

logger = logging.getLogger(__name__)




# --- Adapters ---------------------------------------------------------------

class ActionAdapter:
    name = "base"

    def execute(self, action: models.Action, params: dict, db: Optional[Session] = None) -> dict:
        raise NotImplementedError


class ManualActionAdapter(ActionAdapter):
    """Records that a human must perform the work. Does not invent results."""

    name = "manual"

    def execute(self, action: models.Action, params: dict, db: Optional[Session] = None) -> dict:
        return {
            "status": "SUCCEEDED",
            "execution_result": (
                f"Manual action logged. Operator must perform: {action.objective}. "
                "No external side-effect claimed by ForgeOS."
            ),
            "verification_state": "UNVERIFIED",
        }


class UnsupportedActionAdapter(ActionAdapter):
    name = "unsupported"

    def execute(self, action: models.Action, params: dict, db: Optional[Session] = None) -> dict:
        return {
            "status": "FAILED",
            "execution_result": None,
            "execution_error": f"UNSUPPORTED action_type={action.action_type}. Requires configuration / future adapter.",
            "verification_state": "UNSUPPORTED",
        }


class SMTPEmailActionAdapter(ActionAdapter):
    """Uses the existing durable outbox for a real SMTP email send.

    The message is queued and dispatched through the same local outbox / dispatcher
    path used by the production mail integration. Success here means the provider
    accepted delivery; it does not mean the recipient converted or paid.
    """

    name = "smtp_email"

    def execute(self, action: models.Action, params: dict, db: Optional[Session] = None) -> dict:
        if db is None:
            raise ValueError("db session is required for SMTP email delivery")

        to_email = params.get("to") or params.get("recipient") or params.get("email")
        if not to_email or "@" not in to_email:
            return {
                "status": "FAILED",
                "execution_result": None,
                "execution_error": "Missing valid recipient email for smtp_email action",
                "verification_state": "FAILED",
            }

        subject = params.get("subject") or f"Forge action: {action.objective}"
        body = params.get("body") or action.objective
        idempotency_key = params.get("idempotency_key") or f"action:{action.id}:smtp_email:{to_email}"

        from app.services import integration_dispatcher, integration_outbox

        delivery = integration_outbox.enqueue(
            db,
            integration_name="smtp",
            operation="send_email",
            idempotency_key=idempotency_key,
            request={
                "to": to_email,
                "subject": subject,
                "body": body,
            },
        )

        try:
            dispatched = integration_dispatcher.dispatch_single_delivery(db, delivery.id)
        except Exception as exc:
            # dispatch_single_delivery records the failure on the delivery row
            # itself (permanent, or transient with backoff) before any exception
            # can escape; re-marking here would double-count attempts and could
            # flip a permanent failure back to QUEUED with a fresh backoff.
            return {
                "status": "FAILED",
                "execution_result": None,
                "execution_error": str(exc),
                "verification_state": "FAILED",
            }

        if dispatched.status not in {"SUCCEEDED", "ACCEPTED_BY_SMTP"}:
            return {
                "status": "FAILED",
                "execution_result": None,
                "execution_error": dispatched.last_error or "SMTP delivery failed closed",
                "verification_state": "FAILED",
            }

        try:
            payload = json.loads(dispatched.response_json) if dispatched.response_json else {}
        except (ValueError, TypeError):
            # The delivery was already accepted and recorded by the
            # dispatcher; a malformed provider payload must not flip the
            # action record to FAILED after a real send.
            payload = {}
        message_id = payload.get("message_id") or payload.get("sid") or "unknown"
        action.external_ref = str(dispatched.id)
        db.flush()

        return {
            "status": "SUCCEEDED",
            "execution_result": (
                f"SMTP delivery accepted by provider; message_id={message_id}. "
                "This confirms adapter execution only, not business outcome or payment."
            ),
            "verification_state": "VERIFIED_SUCCESS",
        }


class ForgeBotResponseActionAdapter(ActionAdapter):
    """Authorization-only boundary for Forge Bot responses; never sends."""

    name = "forge_bot_response"

    def execute(
        self,
        action: models.Action,
        params: dict,
        db: Optional[Session] = None,
    ) -> dict:
        if db is None:
            return _failed("A database session is required for Forge Bot response authorization")
        from app.services import forge_bot_response

        return forge_bot_response.execute_response_action(db, action=action)


class GitHubBountyActionAdapter(ActionAdapter):
    """Executes or verifies GitHub bounty actions.
    
    Fails closed if GITHUB_TOKEN is not configured for state mutations.
    Verifies PR merge status independently using public GitHub API.
    """
    name = "github_bounty"

    def execute(self, action: models.Action, params: dict, db: Optional[Session] = None) -> dict:
        from app.services import github_bounty

        action_type = action.action_type
        if action_type == "github_bounty_claim":
            owner = params.get("owner")
            repo = params.get("repo")
            issue_number = params.get("issue_number")
            command = params.get("claim_command", "/attempt")

            if not owner or not repo or not issue_number:
                return {
                    "status": "FAILED",
                    "execution_error": "Missing owner, repo, or issue_number parameter",
                    "verification_state": "FAILED",
                }

            try:
                result = github_bounty.post_bounty_claim_comment(
                    owner=owner,
                    repo=repo,
                    issue_number=int(issue_number),
                    claim_command=command,
                )
                return {
                    "status": "SUCCEEDED",
                    "execution_result": f"Claim comment posted: {result.get('html_url')}",
                    "verification_state": "CLAIMED",
                }
            except ValueError as exc:
                return {
                    "status": "FAILED",
                    "execution_error": str(exc),
                    "verification_state": "CREDENTIALS_REQUIRED",
                }
            except Exception as exc:
                return {
                    "status": "FAILED",
                    "execution_error": f"GitHub API error: {exc}",
                    "verification_state": "API_ERROR",
                }

        elif action_type == "github_bounty_verify":
            owner = params.get("owner")
            repo = params.get("repo")
            pull_number = params.get("pull_number")

            if not owner or not repo or not pull_number:
                return {
                    "status": "FAILED",
                    "execution_error": "Missing owner, repo, or pull_number parameter",
                    "verification_state": "FAILED",
                }

            res = github_bounty.verify_pr_merge_status(owner=owner, repo=repo, pull_number=int(pull_number))
            if res.get("merged"):
                return {
                    "status": "SUCCEEDED",
                    "execution_result": f"PR #{pull_number} merged! Commit SHA: {res.get('merge_commit_sha')}",
                    "verification_state": "VERIFIED",
                }
            else:
                return {
                    "status": "FAILED" if res.get("state") == "closed" else "RUNNING",
                    "execution_result": f"PR #{pull_number} is {res.get('status')}",
                    "verification_state": "UNVERIFIED",
                }

        return {
            "status": "FAILED",
            "execution_error": f"UNSUPPORTED github bounty action_type={action_type}",
            "verification_state": "UNSUPPORTED",
        }


class ProviderNetworkAdapter(ActionAdapter):
    """Writes the existing public provider records. Never publishes without a separate approved action."""

    name = "provider_network"

    def execute(self, action: models.Action, params: dict, db: Optional[Session] = None) -> dict:
        if db is None:
            return _failed("A database session is required")
        kind = action.action_type
        if kind == "provider_candidate":
            return self._candidate(action, params, db)
        if kind == "provider_verify":
            return self._verify(action, params, db)
        if kind == "provider_publish":
            return self._publish(action, params, db)
        return _failed(f"UNSUPPORTED action_type={kind}")

    def _candidate(self, action: models.Action, params: dict, db: Session) -> dict:
        name = _text(params.get("name"))
        if not name:
            return _failed("Candidate name is required")
        provider = models.Provider(
            name=name,
            business_name=_text(params.get("business_name")),
            category=_text(params.get("category")),
            summary=_text(params.get("summary")),
            city=_text(params.get("city")),
            region=_text(params.get("region")),
            country=_text(params.get("country")) or "Nepal",
            phone=_text(params.get("phone")),
            email=_text(params.get("email")),
            is_active=True,
            public_visible=False,
            verification_status="unverified",
        )
        db.add(provider)
        db.flush()
        action.external_ref = str(provider.id)
        return {
            "status": "SUCCEEDED",
            "execution_result": f"provider_id={provider.id} unverified non-public",
            "verification_state": "UNVERIFIED",
        }

    def _verify(self, action: models.Action, params: dict, db: Session) -> dict:
        provider = _provider(db, params.get("provider_id") or action.external_ref)
        evidence_type = _text(params.get("evidence_type"))
        evidence_reference = _text(params.get("evidence_reference"))
        reviewed_by = _text(params.get("reviewed_by"))
        if provider is None or not evidence_type or not evidence_reference or not reviewed_by:
            return _failed("Verification requires a provider and evidence_type, evidence_reference, reviewed_by")
        record = models.VerificationRecord(
            provider_id=provider.id,
            verification_status="verified",
            evidence_type=evidence_type,
            evidence_reference=evidence_reference,
            reviewed_by=reviewed_by,
            notes=_text(params.get("notes")),
            verified_at=utcnow(),
        )
        provider.verification_status = "verified"
        provider.verification_notes = _text(params.get("notes"))
        provider.public_visible = False
        db.add(record)
        db.flush()
        action.external_ref = str(provider.id)
        return {
            "status": "SUCCEEDED",
            "execution_result": f"provider_id={provider.id} verified, not public",
            "verification_state": "UNVERIFIED",
        }

    def _publish(self, action: models.Action, params: dict, db: Session) -> dict:
        provider = _provider(db, params.get("provider_id") or action.external_ref)
        if provider is None:
            return _failed("Publication requires an existing provider")
        if provider.verification_status != "verified":
            return _failed("Provider is not verified")
        title = _text(params.get("service_title"))
        description = _text(params.get("service_description"))
        availability = _text(params.get("availability_status"))
        listing = None
        if title or description or availability or params.get("price_from"):
            if not title or not description or not availability:
                return _failed("A listing needs a stated title, description, and availability")
            listing = models.ServiceListing(
                provider_id=provider.id,
                title=title,
                description=description,
                category=_text(params.get("category")) or provider.category,
                location=_text(params.get("location")) or provider.city,
                price_from=_text(params.get("price_from")),
                currency=_text(params.get("currency")) or "NPR",
                availability_status=availability,
                is_active=True,
                public_visible=True,
            )
            db.add(listing)
        provider.public_visible = True
        db.flush()
        action.external_ref = str(provider.id)
        listing_note = f" listing_id={listing.id}" if listing is not None else ""
        return {
            "status": "SUCCEEDED",
            "execution_result": f"provider_id={provider.id} public{listing_note}",
            "verification_state": "UNVERIFIED",
        }


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _provider(db: Session, provider_id: Any) -> Optional[models.Provider]:
    if provider_id is None or str(provider_id).strip() == "":
        return None
    try:
        return db.get(models.Provider, int(provider_id))
    except (TypeError, ValueError):
        return None


def _failed(message: str) -> dict:
    return {
        "status": "FAILED",
        "execution_result": None,
        "execution_error": message,
        "verification_state": "FAILED",
    }


ADAPTERS: dict[str, ActionAdapter] = {
    "manual_note": ManualActionAdapter(),
    "manual": ManualActionAdapter(),
    "interview": ManualActionAdapter(),
    "outreach": ManualActionAdapter(),  # outreach is manual unless a real adapter is explicitly selected
    "research": ManualActionAdapter(),
    "provider_candidate": ProviderNetworkAdapter(),
    "provider_verify": ProviderNetworkAdapter(),
    "provider_publish": ProviderNetworkAdapter(),
    "email": SMTPEmailActionAdapter(),
    "smtp_email": SMTPEmailActionAdapter(),
    "forge_bot_response": ForgeBotResponseActionAdapter(),
    "github_bounty_claim": GitHubBountyActionAdapter(),
    "github_bounty_verify": GitHubBountyActionAdapter(),
}


def get_adapter(action_type: str) -> ActionAdapter:
    return ADAPTERS.get(action_type, UnsupportedActionAdapter())


# --- Execution-boundary operation adapters (autonomy step 1, E1) -----------
# The gate (execution_engine.execute_through_gate) calls ONLY these adapters,
# and ONLY through get_operation_adapter. An operation with no entry here is
# REFUSED by the gate: no fallback, no dynamic import, no adapter by name.
#
# Adapter contract (what the gate and the postcondition checkers rely on):
#   adapter(db, action, repo_root=Path) -> dict
#   - action is a BoundaryAction whose scope the gate has already resolved
#     to an ABSOLUTE path for file operations (OP-01/02/04/05) and test-suite
#     paths (OP-03). Adapters still verify the path is inside repo_root.
#   - A dict containing "error" means the operation could not succeed as
#     specified (missing file, protected file, task not found, ...). The gate
#     treats it as a FAILED attempt and does NOT retry it.
#   - Raising means an unexpected environment fault; the gate retries those
#     within its bounded budget, then records failure.
#   - Every adapter result is checked INDEPENDENTLY by postcondition.py
#     against durable state the gate snapshotted BEFORE the adapter ran.
#     An adapter that lies about what it did is caught, not trusted.
#   - No adapter here moves money, contacts anyone, publishes anything,
#     touches a secret, deploys, or reaches the network. OP-03 runs only
#     pytest, inside the repo, via subprocess with a fixed argv (no shell).

# Files the gate never lets an adapter edit or create, even if rights said
# otherwise. This duplicates decision_rights._PROTECTED_PATHS on purpose:
# the gate is the authority and this is the adapter's own second check, so
# a directly-called adapter is safe too. C4 asserts the two lists match.
_OPERATION_PROTECTED_PATHS = frozenset({
    "HANDOFF.md",
    "STATE.md",
    "QUEUE.md",
    "docs/CAPABILITY_QUEUE.md",
    "DOCKER_COMMANDS.md",
})

# Largest file whose content an inspect returns inline; bigger files return
# only their hash and size (the caller re-reads them if it needs the text).
_INSPECT_INLINE_LIMIT = 100_000


def _adapter_error(reason: str) -> dict:
    return {"error": reason}


def _path_inside_root(repo_root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


def _file_scope(action: BoundaryAction, repo_root: Path) -> Path | None:
    """Resolve action.scope to a path inside the repo for file operations.

    Returns None when the scope is not a path inside the repo. The gate
    already resolved it to an absolute path; this is the adapter's own
    verification, so a wrong scope can never escape the repo.
    """
    candidate = Path(action.scope)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    if not _path_inside_root(repo_root, candidate):
        return None
    return candidate


def _is_protected_file(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return True  # outside the repo counts as protected: refuse
    return rel in _OPERATION_PROTECTED_PATHS


def _op_inspect_file(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    path = _file_scope(action, repo_root)
    if path is None:
        return _adapter_error(f"inspect_file scope outside repo: {action.scope}")
    if not path.is_file():
        return _adapter_error(f"inspect_file not a file: {path}")
    data = path.read_bytes()
    result: dict = {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }
    if len(data) <= _INSPECT_INLINE_LIMIT:
        result["content"] = data.decode("utf-8", errors="replace")
    else:
        result["truncated"] = True
    return result


def _op_inspect_repo_state(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    scope = _file_scope(action, repo_root)
    if scope is None:
        return _adapter_error(f"inspect_repo_state scope outside repo: {action.scope}")
    target = scope if scope.is_dir() else repo_root
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", str(target)],
            cwd=str(repo_root), capture_output=True, text=True, timeout=30,
        )
        diffstat = subprocess.run(
            ["git", "diff", "--stat", "--", str(target)],
            cwd=str(repo_root), capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return _adapter_error("inspect_repo_state git command timed out")
    if status.returncode != 0:
        return _adapter_error("inspect_repo_state is not a git repository")
    lines = [line for line in status.stdout.splitlines() if line.strip()]
    return {
        "summary": f"{len(lines)} changed path(s) under {target}",
        "status_lines": lines,
        "diff_stat": diffstat.stdout,
    }


def _op_run_local_tests(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    payload = action.payload or {}
    command = payload.get("command")
    output_rel = payload.get("output_path")
    record_rel = payload.get("run_record_path")
    if not isinstance(command, list) or not command:
        return _adapter_error("run_local_tests payload.command must be a non-empty list")
    # Only pytest, inside the repo, no shell. Anything else is not a test run
    # this boundary knows how to verify, so it is refused here, not run.
    if command[0] == "pytest":
        argv = ["pytest"] + list(command[1:])
    elif command[0] in ("python", "python3") and len(command) >= 3 and command[1] == "-m" and command[2] == "pytest":
        argv = list(command)
    else:
        return _adapter_error("run_local_tests runs pytest only")
    if not isinstance(output_rel, str) or not isinstance(record_rel, str):
        return _adapter_error("run_local_tests needs output_path and run_record_path")
    output_path = repo_root / output_rel
    record_path = repo_root / record_rel
    if not _path_inside_root(repo_root, output_path) or not _path_inside_root(repo_root, record_path):
        return _adapter_error("run_local_tests output paths must stay inside the repo")
    timeout_s = payload.get("timeout_s", 300)
    if not isinstance(timeout_s, (int, float)) or timeout_s <= 0 or timeout_s > 3600:
        return _adapter_error("run_local_tests timeout_s must be within 1..3600")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    import time

    started = time.time()
    try:
        proc = subprocess.run(
            argv, cwd=str(repo_root), timeout=timeout_s,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        exit_code = proc.returncode
        output_text = proc.stdout or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = -1
        output_text = exc.stdout or ""
        if isinstance(output_text, bytes):
            output_text = output_text.decode("utf-8", errors="replace")
        output_text += "\n[run_local_tests: pytest timed out]"
    output_path.write_text(output_text, encoding="utf-8")
    record = {
        "command": argv,
        "exit_code": exit_code,
        "output_path": str(output_path),
        "duration_s": round(time.time() - started, 3),
    }
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {
        "exit_code": exit_code,
        "run_record_path": str(record_path),
        "output_path": str(output_path),
    }


def _op_edit_repo_file(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    path = _file_scope(action, repo_root)
    if path is None:
        return _adapter_error(f"edit_repo_file scope outside repo: {action.scope}")
    if _is_protected_file(path, repo_root):
        return _adapter_error(f"edit_repo_file refused: protected file {path}")
    payload = action.payload or {}
    old_text = payload.get("old_text")
    new_text = payload.get("new_text")
    if not isinstance(old_text, str) or old_text == "" or not isinstance(new_text, str):
        return _adapter_error("edit_repo_file needs non-empty old_text and new_text")
    if not path.is_file():
        return _adapter_error(f"edit_repo_file not a file: {path}")
    text = path.read_text(encoding="utf-8")
    count = text.count(old_text)
    if count == 0:
        return _adapter_error("edit_repo_file old_text not found")
    if count > 1:
        return _adapter_error(f"edit_repo_file old_text ambiguous: {count} occurrences")
    updated = text.replace(old_text, new_text, 1)
    path.write_text(updated, encoding="utf-8")
    return {
        "path": str(path),
        "expected_sha256": hashlib.sha256(updated.encode("utf-8")).hexdigest(),
    }


def _op_create_repo_file(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    path = _file_scope(action, repo_root)
    if path is None:
        return _adapter_error(f"create_repo_file scope outside repo: {action.scope}")
    if _is_protected_file(path, repo_root):
        return _adapter_error(f"create_repo_file refused: protected file {path}")
    payload = action.payload or {}
    content = payload.get("content")
    if not isinstance(content, str):
        return _adapter_error("create_repo_file needs content")
    if path.exists():
        return _adapter_error(f"create_repo_file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "path": str(path),
        "expected_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def _op_record_event(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    payload = action.payload or {}
    event_type = payload.get("event_type")
    source = payload.get("source")
    if not isinstance(event_type, str) or not event_type:
        return _adapter_error("record_event needs event_type")
    if not isinstance(source, str) or not source:
        return _adapter_error("record_event needs source")
    event_payload = payload.get("payload") or {}
    if not isinstance(event_payload, dict):
        return _adapter_error("record_event payload must be an object")
    event = models.WorldEvent(
        event_type=event_type,
        source=source,
        payload=json.dumps(event_payload, sort_keys=True),
    )
    db.add(event)
    db.flush()
    return {
        "event_id": event.id,
        "fields": {"event_type": event_type, "source": source},
    }


def _op_read_task_state(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    payload = action.payload or {}
    task_id = payload.get("task_id")
    if not isinstance(task_id, int):
        return _adapter_error("read_task_state needs integer task_id")
    task = db.query(models.WorkerTask).filter_by(id=task_id).first()
    if task is None:
        return _adapter_error(f"read_task_state task not found: {task_id}")
    return {
        "task_id": task.id,
        "status": task.status,
        "attempts": task.attempts,
        "worker_type": task.worker_type,
        "task_name": task.task_name,
    }


def _op_requeue_task(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    payload = action.payload or {}
    task_id = payload.get("task_id")
    checkpoint_id = payload.get("checkpoint_id")
    if not isinstance(task_id, int):
        return _adapter_error("requeue_task needs integer task_id")
    if not isinstance(checkpoint_id, str) or not checkpoint_id:
        return _adapter_error("requeue_task needs checkpoint_id")
    task = db.query(models.WorkerTask).filter_by(id=task_id).first()
    if task is None:
        return _adapter_error(f"requeue_task task not found: {task_id}")
    if task.attempts >= task.max_attempts:
        return _adapter_error(f"requeue_task attempts exhausted: {task.attempts}/{task.max_attempts}")
    evidence = dict(task.evidence or {})
    evidence["checkpoint_id"] = checkpoint_id
    evidence["requeued_at"] = utcnow().isoformat()
    task.evidence = evidence
    task.status = "queued"
    task.attempts = task.attempts + 1
    db.flush()
    return {
        "task_id": task.id,
        "status": task.status,
        "attempts": task.attempts,
        "checkpoint_id": checkpoint_id,
    }


def _op_open_blocker(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    payload = action.payload or {}
    task_id = payload.get("task_id")
    reason = payload.get("reason")
    if not isinstance(task_id, int):
        return _adapter_error("open_blocker needs integer task_id")
    if not isinstance(reason, str) or not reason:
        return _adapter_error("open_blocker needs reason")
    task = db.query(models.WorkerTask).filter_by(id=task_id).first()
    if task is None:
        return _adapter_error(f"open_blocker task not found: {task_id}")
    task.status = "blocked"
    task.error = reason
    event = models.WorldEvent(
        event_type="blocker_opened",
        source="execution_boundary",
        payload=json.dumps({"task_id": task.id, "reason": reason}, sort_keys=True),
    )
    db.add(event)
    db.flush()
    return {"task_id": task.id, "event_id": event.id}


def _op_read_halt_state(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    row = db.query(models.OpHamiRuntimeControl).first()
    if row is None:
        return {"halted": True}  # no HALT record: fail closed, as if halted
    return {"halted": bool(row.safe_mode_enabled)}


def _op_send_delivery(db: Session, action: BoundaryAction, repo_root: Path) -> dict:
    from app.services import integration_dispatcher

    return integration_dispatcher.execute_gated_delivery(db, action)


# Closed registry: every operation the gate may execute, and nothing else.
# The gate REFUSES any operation not present here (get_operation_adapter
# returns None) instead of falling back to any other adapter.
OPERATION_ADAPTERS: dict[Operation, Callable] = {
    Operation.INSPECT_FILE: _op_inspect_file,
    Operation.INSPECT_REPO_STATE: _op_inspect_repo_state,
    Operation.RUN_LOCAL_TESTS: _op_run_local_tests,
    Operation.EDIT_REPO_FILE: _op_edit_repo_file,
    Operation.CREATE_REPO_FILE: _op_create_repo_file,
    Operation.RECORD_EVENT: _op_record_event,
    Operation.READ_TASK_STATE: _op_read_task_state,
    Operation.REQUEUE_TASK: _op_requeue_task,
    Operation.OPEN_BLOCKER: _op_open_blocker,
    Operation.READ_HALT_STATE: _op_read_halt_state,
    Operation.SEND_EMAIL: _op_send_delivery,
    Operation.SEND_SMS: _op_send_delivery,
    Operation.SEND_TELEGRAM: _op_send_delivery,
}


def get_operation_adapter(operation) -> Callable | None:
    """Return the adapter for a boundary operation, or None when unknown.

    Accepts an Operation or its string value. Unknown operations return
    None — the gate refuses them; there is no fallback adapter.
    """
    if isinstance(operation, str):
        try:
            operation = Operation(operation)
        except ValueError:
            return None
    if not isinstance(operation, Operation):
        return None
    return OPERATION_ADAPTERS.get(operation)


# --- Lifecycle --------------------------------------------------------------

def propose_action(
    db: Session,
    *,
    objective: str,
    action_type: str = "manual_note",
    decision_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
    experiment_id: Optional[int] = None,
    goal_id: Optional[int] = None,
    parameters: Optional[dict] = None,
    estimated_cost: float = 0.0,
    risk_score: float = 20.0,
) -> models.Action:
    """Create action, evaluate policy, set PROPOSED / APPROVAL_REQUIRED / BLOCKED."""
    if action_type == "forge_bot_response":
        raise ValueError(
            "Use forge_bot_response.propose_response_action for owner-gated response ACTIONs"
        )
    # Reuse autonomy policy evaluation shape via a lightweight probe on Experiment
    # path when available; otherwise simple rules.
    policy_result = "ALLOW"
    policy_reason = "Low-risk manual/research action"

    if action_type in ("outreach", "email", "http_request", "provider_verify", "provider_publish") or estimated_cost > 0:
        policy_result = "REQUIRE_APPROVAL"
        policy_reason = "External contact, publication, or cost requires owner approval"
    if action_type in ("execute_trade", "broker_order", "wire_transfer"):
        policy_result = "BLOCK"
        policy_reason = "High-risk financial action blocked by default policy"

    # Opportunity actions use the database-backed policy evaluator. The
    # alias keeps the adapter vocabulary compatible with the experiment path.
    opportunity = db.query(models.Opportunity).filter_by(id=opportunity_id).first() if opportunity_id else None
    if opportunity:
        policy_action_type = "customer_interview" if action_type == "interview" else action_type
        try:
            evaluation = autonomy_engine.evaluate_action(
                db, opportunity, policy_action_type, estimated_cost
            )
            policy_result = {
                "allow": "ALLOW",
                "require_approval": "REQUIRE_APPROVAL",
                "block": "BLOCK",
            }[evaluation["decision"]]
            policy_reason = " ".join(evaluation["reasons"])
        except Exception as exc:
            policy_result = "BLOCK"
            policy_reason = f"Policy evaluation failed closed: {exc}"

    # Central rights guard is stricter than generic risk policy. It runs after
    # policy evaluation so no ALLOW can erase owner-only rights.
    rights_gate = decision_rights.enforcement_for(action_type)
    if rights_gate["requires_owner_approval"] and policy_result != "BLOCK":
        policy_result = "REQUIRE_APPROVAL"
        existing_reason = policy_reason or ""
        if rights_gate["enforcement_reason"] not in existing_reason:
            policy_reason = (existing_reason + " " + rights_gate["enforcement_reason"]).strip()

    status = "PROPOSED"
    if policy_result == "REQUIRE_APPROVAL":
        status = "APPROVAL_REQUIRED"
    elif policy_result == "BLOCK":
        status = "CANCELLED"

    stored_parameters = dict(parameters or {})
    # Persist the canonical cost argument so a standing-authorization envelope
    # cannot accidentally treat a cost-bearing action as zero-cost.
    stored_parameters["estimated_cost"] = estimated_cost if estimated_cost is not None else 0.0

    action = models.Action(
        decision_id=decision_id,
        opportunity_id=opportunity_id,
        strategy_id=strategy_id,
        experiment_id=experiment_id,
        goal_id=goal_id,
        action_type=action_type,
        objective=objective,
        parameters_json=json.dumps(stored_parameters),
        status=status,
        policy_result=policy_result,
        policy_reason=policy_reason,
        adapter_name=get_adapter(action_type).name,
        verification_state="UNVERIFIED",
    )
    # Standing authorization: if policy_result is REQUIRE_APPROVAL specifically
    # for owner approval (not a policy violation or block), an ACTIVE bounded
    # standing authorization may satisfy it. BLOCK is never touched.
    if (
        policy_result == "REQUIRE_APPROVAL"
        or decision_rights.entry_for(action_type).get("requires_standing_authorization")
    ):
        # Consent-bound action types must always traverse the envelope check,
        # including when generic policy evaluation initially returned ALLOW.
        action = autonomy_engine.apply_standing_authorization_to_action(db, action)
        policy_result = action.policy_result
        policy_reason = action.policy_reason
        status = action.status
    if policy_result == "BLOCK":
        action.execution_error = policy_reason

    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def approve_action(db: Session, action_id: int) -> Optional[models.Action]:
    action = db.query(models.Action).filter_by(id=action_id).first()
    if not action:
        return None
    if action.policy_result == "BLOCK":
        return action  # cannot approve blocked
    from app.services import intervention_gate

    intervention_gate.assert_single_active_intervention(db, action)
    action.status = "APPROVED"
    action.approved_at = utcnow()
    db.commit()
    db.refresh(action)
    return action


def start_and_execute_action(db: Session, action_id: int) -> Optional[models.Action]:
    action = db.query(models.Action).filter_by(id=action_id).first()
    if not action:
        return None
    if action.status == "APPROVAL_REQUIRED":
        action.execution_error = "Requires owner approval before start"
        db.commit()
        return action
    if action.status not in ("PROPOSED", "APPROVED"):
        return action
    if action.policy_result == "BLOCK":
        action.status = "CANCELLED"
        action.execution_error = action.policy_reason
        db.commit()
        return action

    # Recheck rights at the final execution boundary. Legacy or directly-mutated
    # ALLOW rows cannot bypass current owner-only or stage-gated rights.
    rights_gate = decision_rights.enforcement_for(action.action_type)
    explicitly_approved = action.status == "APPROVED" and action.approved_at is not None
    if rights_gate["requires_owner_approval"] and not explicitly_approved:
        action.status = "APPROVAL_REQUIRED"
        action.policy_result = "REQUIRE_APPROVAL"
        action.policy_reason = rights_gate["enforcement_reason"]
        action.execution_error = "Decision-rights gate requires explicit owner approval."
        db.commit()
        db.refresh(action)
        return action

    # Revalidate the active standing-authorization envelope immediately before
    # adapter dispatch. Proposal-time ALLOW and an owner-approved status are
    # not substitutes for a current bounded authorization for these action
    # classes. The customer response adapter retains separate consent/template
    # checks as a second, recipient-specific boundary.
    params = {}
    if rights_gate.get("requires_standing_authorization"):
        try:
            params = json.loads(action.parameters_json) if action.parameters_json else {}
            if not isinstance(params, dict):
                raise ValueError("Action parameters must be a JSON object")
        except Exception:
            params = {}
        auth_id = params.get("standing_auth_id") if isinstance(params, dict) else None
        auth = db.get(models.Action, auth_id) if type(auth_id) is int else None
        if auth is not None and auth.status == "ACTIVE":
            active = autonomy_engine.get_active_standing_authorizations(db, action.action_type)
            if any(row.id == auth_id for row in active):
                bounded_params = dict(params)
                bounded_params["objective"] = action.objective
                bounded_params["estimated_cost"] = bounded_params.get("estimated_cost", 0.0)
                bounded_params["data_scope"] = bounded_params.get("data_scope") or "REAL"
                matched, _ = autonomy_engine.matches_standing_envelope(
                    db,
                    auth,
                    action.action_type,
                    bounded_params,
                    exclude_action_id=action.id,
                )
                if matched:
                    params = bounded_params
                else:
                    auth = None
            else:
                auth = None
        if auth is None:
            detail = "No current matching ACTIVE standing authorization; dispatch refused."
            action.status = "APPROVAL_REQUIRED"
            action.policy_result = "REQUIRE_APPROVAL"
            action.policy_reason = "decision_rights:standing_authorization_required — " + detail
            action.execution_error = detail
            db.commit()
            db.refresh(action)
            return action

    from app.services import intervention_gate

    intervention_gate.assert_single_active_intervention(db, action)
    action.status = "RUNNING"
    action.started_at = utcnow()
    db.commit()

    try:
        if not params:
            params = json.loads(action.parameters_json) if action.parameters_json else {}
        if not isinstance(params, dict):
            raise ValueError("Action parameters must be a JSON object")
        adapter = get_adapter(action.action_type)
        result = adapter.execute(action, params, db=db)
    except Exception as exc:
        result = {
            "status": "FAILED",
            "execution_result": None,
            "execution_error": f"Execution failed closed: {exc}",
            "verification_state": "FAILED",
        }

    action.completed_at = utcnow()
    action.execution_result = result.get("execution_result")
    action.execution_error = result.get("execution_error")
    action.verification_state = result.get("verification_state", "UNVERIFIED")
    st = result.get("status", "FAILED")
    if st == "SUCCEEDED":
        action.status = "SUCCEEDED"
    else:
        action.status = "FAILED"

    db.commit()
    db.refresh(action)
    return action


def propagate_verified_learning_for_outcome(db: Session, outcome_id: int) -> None:
    """Apply the existing evidence-gated learning loop after an Outcome is committed.

    The helper is intentionally narrow: only REAL + REAL-source + VERIFIED
    outcomes can reach apply_learning_to_system(). Reported, test, mock,
    sandbox, disputed, and hypothetical records remain history only.
    Failures are logged without turning an already-committed payment/outcome
    into an apparent write failure; an idempotent replay can retry this step.
    """
    from app import evidence_source
    from app.services import learning_engine

    try:
        outcome = db.get(models.Outcome, outcome_id)
        if (
            outcome is None
            or outcome.data_scope != "REAL"
            or not evidence_source.is_real(outcome.source_kind)
            or outcome.verification_state != "VERIFIED"
        ):
            return

        events = (
            db.query(models.LearningEvent)
            .filter_by(
                outcome_id=outcome.id,
                data_scope="REAL",
                source_kind=evidence_source.REAL,
            )
            .order_by(models.LearningEvent.id.asc())
            .all()
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Verified outcome learning lookup failed; outcome_id=%s",
            outcome_id,
        )
        return

    for event in events:
        try:
            learning_engine.apply_learning_to_system(db, event)
        except Exception:
            db.rollback()
            logger.exception(
                "Verified outcome learning propagation failed; outcome_id=%s learning_event_id=%s",
                outcome.id,
                event.id,
            )


def record_outcome(
    db: Session,
    *,
    outcome_type: str,
    action_id: Optional[int] = None,
    experiment_id: Optional[int] = None,
    decision_id: Optional[int] = None,
    product_id: Optional[int] = None,
    actual_value: Optional[float] = None,
    unit: Optional[str] = None,
    qualitative_result: Optional[str] = None,
    source: str = "manual",
    success: Optional[bool] = None,
    notes: Optional[str] = None,
    data_scope: str = "REAL",
    source_kind: str = "MOCK",
    verification_state: str = "REPORTED",
    idempotency_key: Optional[str] = None,
    commit: bool = True,
) -> models.Outcome:
    """Append an explicit outcome and product learning atomically; never estimate cash."""
    import math
    from app import evidence_source
    from app.services import lessons_engine
    data_scope = data_scope.strip().upper()
    if data_scope not in {"REAL", "SANDBOX"}:
        raise ValueError("Invalid data scope")
    source_kind = evidence_source.validate(source_kind)
    verification_state = verification_state.strip().upper()
    if verification_state not in {"REPORTED", "VERIFIED", "DISPUTED"}:
        raise ValueError("Invalid verification state")
    if evidence_source.is_real(source_kind) and verification_state != "VERIFIED":
        raise ValueError(
            "REAL outcomes require VERIFIED proof; refusing to label unverified data REAL"
        )
    if outcome_type not in {"ACTUAL_REVENUE", "ACTUAL_COST", "ACTUAL_RESPONSE", "ACTUAL_CUSTOMERS", "ACTUAL_CONVERSION", "QUALITATIVE", "OTHER"}:
        raise ValueError("Invalid outcome type")
    if actual_value is not None and (not math.isfinite(actual_value) or actual_value < 0):
        raise ValueError("Actual values must be finite and nonnegative")
    if outcome_type in {"ACTUAL_REVENUE", "ACTUAL_COST"}:
        if actual_value is None:
            raise ValueError("An explicit collected/spent amount is required")
        currency = (unit or "USD").upper()
        if currency not in {"USD", "NPR"}:
            raise ValueError("Revenue/cost outcomes currently support USD or NPR; currencies are never auto-converted")
        if outcome_type == "ACTUAL_REVENUE" and currency == "NPR" and data_scope == "SANDBOX":
            raise ValueError("NPR revenue must come from the REAL provider-verified payment flow; sandbox revenue cannot be represented as NPR cash.")
        unit = currency
    product = db.get(models.Product, product_id) if product_id else None
    if product_id and (not product or product.data_scope != data_scope):
        raise ValueError("Product not found or data scope mismatch")
    exp = db.get(models.Experiment, experiment_id) if experiment_id else None
    if experiment_id:
        if not exp or exp.data_scope != data_scope:
            raise ValueError("Experiment not found or data scope mismatch")
        if exp.status in ("blocked", "abandoned") or (exp.requires_owner_approval and not exp.approved_at):
            raise ValueError("Experiment approval is required")
        if exp.action_type == "customer_interview" and not exp.started_at:
            raise ValueError("Human execution must be recorded first")
    if action_id and not db.get(models.Action, action_id):
        raise ValueError("Action not found")
    marker = "idempotency:" + idempotency_key if idempotency_key else None
    if marker:
        existing = db.query(models.Outcome).filter_by(notes=marker, data_scope=data_scope).first()
        if existing:
            if (existing.outcome_type, existing.product_id, existing.experiment_id, existing.actual_value) != (outcome_type, product_id, experiment_id, actual_value):
                raise ValueError("Conflicting idempotency key")
            if commit:
                propagate_verified_learning_for_outcome(db, existing.id)
            return existing
    try:
        outcome = models.Outcome(action_id=action_id, experiment_id=experiment_id,
            decision_id=decision_id, product_id=product_id, outcome_type=outcome_type,
            actual_value=actual_value, unit=unit, qualitative_result=qualitative_result,
            source=source, success=success, verification_state=verification_state,
            notes=marker or notes, data_scope=data_scope, source_kind=source_kind)
        db.add(outcome)
        db.flush()
        if action_id and success is not None:
            action = db.get(models.Action, action_id)
            if action.status == "SUCCEEDED":
                action.status = "VERIFIED"
                action.verification_state = "VERIFIED_SUCCESS" if success else "VERIFIED_FAILURE"
        if product:
            event = models.LearningEvent(product_id=product_id, outcome_id=outcome.id,
                opportunity_id=product.opportunity_id,
                prediction=product.hypothesis or product.offer,
                actual=f"{outcome_type}: {actual_value} {unit or ''}. {qualitative_result or ''} [{source_kind}/{verification_state}]",
                lesson=(
                    f"[{data_scope}/{source_kind}/{verification_state}] "
                    f"Recorded {outcome_type} from outcome #{outcome.id}. "
                    "Compare this observation with the prediction; one event does not prove market demand."
                ),
                error_type="confirmed" if success else None, data_scope=data_scope,
                source_kind=outcome.source_kind,
                belief_update_applied=False)
            db.add(event)
            db.flush()
            lessons_engine.consolidate_learning_event(db, event, commit=False)
        if commit:
            db.commit()
            propagate_verified_learning_for_outcome(db, outcome.id)
        return outcome
    except Exception:
        db.rollback()
        raise


def record_domain_event(
    db: Session,
    *,
    idempotency_key: str,
    qualitative_result: str,
    source: str,
    success: Optional[bool] = None,
    actual_value: Optional[float] = None,
    unit: Optional[str] = None,
    commit: bool = True,
) -> models.Outcome:
    """Write one of our own events into the existing outcome record. No revenue is inferred.

    Set commit=False when a caller must commit the state transition and this
    event as one transaction. The default preserves existing call semantics.
    """
    return record_outcome(
        db,
        outcome_type="QUALITATIVE",
        qualitative_result=qualitative_result,
        source=source,
        success=success,
        actual_value=actual_value,
        unit=unit,
        idempotency_key=idempotency_key,
        data_scope="REAL",
        commit=commit,
    )


def list_actions(db: Session, limit: int = 50) -> list[models.Action]:
    return db.query(models.Action).order_by(models.Action.proposed_at.desc()).limit(limit).all()


def list_outcomes(db: Session, limit: int = 50) -> list[models.Outcome]:
    return db.query(models.Outcome).order_by(models.Outcome.observed_at.desc()).limit(limit).all()


def actions_from_decision(db: Session, decision_id: int, count: int = 1) -> list[models.Action]:
    """Materialize concrete actions from an accepted decision."""
    decision = db.query(models.Decision).filter_by(id=decision_id).first()
    if not decision:
        return []
    created = []
    for i in range(count):
        a = propose_action(
            db,
            objective=f"{decision.title} — step {i+1}",
            action_type="interview" if "interview" in (decision.title or "").lower() else "manual_note",
            decision_id=decision.id,
            opportunity_id=decision.opportunity_id,
            strategy_id=decision.strategy_id,
            goal_id=decision.goal_id,
            parameters={"step": i + 1, "from_decision": decision.id},
        )
        created.append(a)
    return created
