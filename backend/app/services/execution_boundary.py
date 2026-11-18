"""Hami Autonomy - Step 1: execution boundary types (C1).

The single vocabulary every other step-1 file uses: the closed typed
operation list, the Action dataclass, and the ExecutionResult / Refusal
types. Types only - no execution logic lives here. See
``docs/AUTONOMY_STEP1.md`` and the step-1 plan (plan section 1b-C1,
section 2 for the operation table).

Step 1 does not invent a second permission system: the Rights values
below are the plan's names for the semantics already in
``decision_rights.py`` (unknown defaults to OWNER_ONLY). The E2 edit
translates between the two where they meet. INTERNAL_SERVICE is limited
to the registered integration dispatcher and send scopes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Operation(str, Enum):
    """The closed operation list (plan section 2).

    If an operation is not listed here, it does not exist for Hami,
    and the gate refuses it as unknown. Adding an operation later is
    a deliberate, recorded change to this list - never an automatic
    inference.
    """

    INSPECT_FILE = "inspect_file"
    INSPECT_REPO_STATE = "inspect_repo_state"
    RUN_LOCAL_TESTS = "run_local_tests"
    EDIT_REPO_FILE = "edit_repo_file"
    CREATE_REPO_FILE = "create_repo_file"
    RECORD_EVENT = "record_event"
    READ_TASK_STATE = "read_task_state"
    REQUEUE_TASK = "requeue_task"
    OPEN_BLOCKER = "open_blocker"
    READ_HALT_STATE = "read_halt_state"
    SEND_EMAIL = "send_email"
    SEND_SMS = "send_sms"
    SEND_TELEGRAM = "send_telegram"


class Rights(str, Enum):
    """Rights values (plan section 2)."""

    OWNER_ONLY = "owner_only"
    AUTHORIZED_SCOPE = "authorized_scope"
    INTERNAL_READ = "internal_read"
    INTERNAL_SERVICE = "internal_service"
    DENIED = "denied"


class Outcome(str, Enum):
    """Postcondition outcomes (plan section 3d)."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    REFUSED = "refused"


class RefusalReason(str, Enum):
    """Structured refusal reasons (plan sections 3b and 4, tests T-02..T-06)."""

    UNKNOWN_OPERATION = "unknown_operation"
    AUTHORIZATION_EXPIRED = "authorization_expired"
    AUTHORIZATION_REVOKED = "authorization_revoked"
    HALT_SET = "halt_set"
    OUT_OF_SCOPE = "out_of_scope"
    NO_ADAPTER = "no_adapter"
    ALREADY_IN_PROGRESS = "already_in_progress"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"
    CIRCUIT_OPEN = "circuit_open"


@dataclass(frozen=True)
class Action:
    """One unit of work to run through the execution gate (plan 1b-C1).

    ``payload`` carries the operation's inputs only - never secrets,
    never credentials. ``idempotency_key`` is computed by the gate (E4),
    never trusted from the caller.
    """

    operation: Operation
    principal: str
    scope: str
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None


@dataclass(frozen=True)
class ExecutionResult:
    """What the gate returns after running (or replaying) an Action."""

    operation: Operation
    principal: str
    outcome: Outcome
    result: Optional[dict[str, Any]] = None
    replayed: bool = False
    evidence_ref: Optional[str] = None
    attempt: int = 1


@dataclass(frozen=True)
class Refusal:
    """A structured refusal (plan section 3b): not an exception, not a success.

    The gate returns this when it never ran the adapter, so a caller
    cannot mistake a refusal for a result or swallow it silently.
    """

    operation: Operation
    principal: str
    reason: RefusalReason
    detail: str = ""
