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

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services import autonomy_engine




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

    status = "PROPOSED"
    if policy_result == "REQUIRE_APPROVAL":
        status = "APPROVAL_REQUIRED"
    elif policy_result == "BLOCK":
        status = "CANCELLED"

    action = models.Action(
        decision_id=decision_id,
        opportunity_id=opportunity_id,
        strategy_id=strategy_id,
        experiment_id=experiment_id,
        goal_id=goal_id,
        action_type=action_type,
        objective=objective,
        parameters_json=json.dumps(parameters or {}),
        status=status,
        policy_result=policy_result,
        policy_reason=policy_reason,
        adapter_name=get_adapter(action_type).name,
        verification_state="UNVERIFIED",
    )
    # Standing authorization: if policy_result is REQUIRE_APPROVAL specifically
    # for owner approval (not a policy violation or block), an ACTIVE bounded
    # standing authorization may satisfy it. BLOCK is never touched.
    if policy_result == "REQUIRE_APPROVAL":
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

    from app.services import intervention_gate

    intervention_gate.assert_single_active_intervention(db, action)
    action.status = "RUNNING"
    action.started_at = utcnow()
    db.commit()

    try:
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
        if unit and unit.upper() != "USD":
            raise ValueError("Dollar rollups currently support USD only; currency conversion is not implemented")
        unit = "USD"
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
            event = models.LearningEvent(product_id=product_id, opportunity_id=product.opportunity_id,
                prediction=product.hypothesis or product.offer,
                actual=f"{outcome_type}: {actual_value} {unit or ''}. {qualitative_result or ''}",
                lesson=f"[{data_scope}] Recorded {outcome_type} from outcome #{outcome.id}. Compare this reported result with the offer; one event does not prove market demand.",
                error_type="confirmed" if success else None, data_scope=data_scope,
                source_kind=outcome.source_kind,
                belief_update_applied=False)
            db.add(event)
            db.flush()
            lessons_engine.consolidate_learning_event(db, event, commit=False)
        if commit:
            db.commit()
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
) -> models.Outcome:
    """Write one of our own events into the existing outcome record. No revenue is inferred."""
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
