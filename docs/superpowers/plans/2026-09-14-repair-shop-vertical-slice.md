# Repair-Shop Vertical Slice Implementation Plan

> **For agentic workers:** This plan is executed inline in the extracted ForgeOS working copy. Assignment-5 and every legacy mirror remain read-only and are never imported as runtime dependencies.

**Goal:** Add one auditable repair-shop work-item workflow to ForgeOS using the existing Opportunity, Decision, Experiment, Action, Evidence, Outcome, LearningEvent, Product, CustomerEvent, IntegrationDelivery, autonomy, and payment-verification boundaries.

**Architecture:** Extend the current SQLAlchemy/FastAPI/Next.js architecture with only the missing repair-shop aggregate records: customer, work item, and work-item transition/audit records. Reuse the existing `Experiment` as the canonical triage/action/experiment execution record, `Evidence` plus `EvidenceRelationship` for evidence linkage, `Decision` for triage rationale, `Action` for approved human/manual actions, `Outcome` for actual response/payment/outcome facts, `LearningEvent` for expected-vs-actual learning, `Product` for the offer/revenue rollup, and existing eSewa/Khalti verification routes for optional real-payment verification. Customer communication remains a reviewed draft/approved/sent state; no automatic customer contact is added.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic, SQLite additive migrations, pytest, Next.js, React, TypeScript, existing ForgeOS styling and API client.

**Spec:** `/home/ubuntu/forgeos-work/P1_INSTRUCTIONS.txt`

## Global Constraints

- Original repositories are archive-first; Assignment-5 is precious, protected, and must not be modified or copied into ForgeOS.
- Do not create a second execution, experiment, revenue, payment, or learning system.
- Actual revenue is recorded only from verified real payment evidence and linked `Outcome` rows with `ACTUAL_REVENUE`; test data must use `SANDBOX`.
- Customer communication defaults to `DRAFT`; the system must not automatically contact a customer.
- Migrations are additive-only and must preserve existing ForgeOS rows, including the 11,847-signal baseline.
- Every transition must retain an ID, timestamp, actor, state, reason, evidence linkage, previous state, and next state.
- Unapproved actions cannot execute; failed payments cannot become actual revenue; customer acceptance is not payment; payment is not a successful outcome.

---

### Task 1: Add repair-shop domain records with additive migrations

**Files:**
- Modify: `backend/app/models.py` near the existing `CustomerEvent`, `IntegrationDelivery`, and lifecycle models.
- Modify: `backend/app/migrations.py` with additive columns/tables only.
- Test: `backend/tests/test_repair_shop_models.py`

**Interfaces:**
- `Customer`: id, name, contact_identifier, consent_state, created_at, data_scope.
- `RepairWorkItem`: id, customer_id, asset_label, reported_problem, status, data_scope, linked opportunity/decision/experiment/action/outcome/product IDs, created_at, updated_at.
- `WorkItemEvent`: id, work_item_id, actor, event_type, previous_state, next_state, reason, evidence_ids, metadata_json, created_at.
- `CustomerCommunication`: id, work_item_id, channel, body, status (`DRAFT|APPROVED|SENT|CUSTOMER_RESPONDED`), customer_response, action_id, integration_delivery_id, created_at, updated_at.
- No payment table is introduced; payment facts are represented by existing `Outcome` plus a verified provider response or explicit manual evidence reference.

- [ ] **Step 1: Write failing model tests**

```python
def test_repair_shop_tables_are_created(db):
    from sqlalchemy import inspect
    from app import models
    tables = set(inspect(db.bind).get_table_names())
    assert {"customers", "repair_work_items", "work_item_events", "customer_communications"} <= tables
```

- [ ] **Step 2: Run the focused test and verify it fails because the tables do not exist.**

Run: `cd backend && python3 -m pytest tests/test_repair_shop_models.py -q`

Expected: FAIL with the new table names absent.

- [ ] **Step 3: Add the four models and relationships.**

Use existing `utcnow`, `data_scope`, SQLAlchemy naming, and foreign-key conventions. Keep all new IDs nullable on `RepairWorkItem` so creation does not fabricate decisions, actions, payments, or outcomes.

- [ ] **Step 4: Add migration entries only where existing tables need new linkage columns.**

Additive migration entries must preserve existing rows and must not rewrite or backfill historical economic records.

- [ ] **Step 5: Run the focused model and migration tests.**

Run: `cd backend && python3 -m pytest tests/test_repair_shop_models.py -q`

Expected: PASS with existing data untouched.

---

### Task 2: Implement the repair-shop service state machine

**Files:**
- Create: `backend/app/services/repair_shop.py`
- Test: `backend/tests/test_repair_shop_service.py`

**Interfaces:**
- `create_work_item(db, customer_name, contact_identifier, consent_state, asset_label, reported_problem, data_scope, actor) -> RepairWorkItem`
- `attach_evidence(db, work_item_id, content, source, data_scope, actor) -> Evidence`
- `create_triage(db, work_item_id, rationale, expected_outcome, confidence, actor) -> tuple[Decision, Experiment]`
- `propose_customer_status(db, work_item_id, body, actor) -> CustomerCommunication`
- `approve_customer_status(db, communication_id, actor) -> CustomerCommunication`
- `record_customer_response(db, communication_id, accepted, response, actor) -> CustomerCommunication`
- `record_verified_payment(db, work_item_id, amount, unit, provider, provider_reference, data_scope, actor) -> Outcome`
- `record_work_outcome(db, work_item_id, actual, success, source, actor) -> tuple[Outcome, LearningEvent]`
- `get_work_item_detail(db, work_item_id) -> dict`

- [ ] **Step 1: Write failing tests for creation, evidence linkage, and truth-preserving state.**

```python
def test_create_work_item_records_observed_problem_and_event(db):
    item = create_work_item(db, "Test Shop", "sandbox-contact", "GRANTED", "Laptop-1", "Will not boot", "SANDBOX", "tester")
    assert item.status == "INTAKE"
    event = db.query(models.WorkItemEvent).filter_by(work_item_id=item.id).one()
    assert event.previous_state is None and event.next_state == "INTAKE"
    assert event.actor == "tester"


def test_attach_evidence_links_evidence_to_work_item(db):
    item = create_work_item(db, "Test Shop", None, "NOT_REQUIRED", "Phone-1", "Cracked screen", "SANDBOX", "tester")
    evidence = attach_evidence(db, item.id, "Photo received", "manual", "SANDBOX", "tester")
    detail = get_work_item_detail(db, item.id)
    assert evidence.id in [entry["evidence_id"] for entry in detail["evidence"]]
```

- [ ] **Step 2: Run the focused service tests to verify failure.**

Run: `cd backend && python3 -m pytest tests/test_repair_shop_service.py -q`

Expected: FAIL because the service module/functions are absent.

- [ ] **Step 3: Implement the minimal state machine.**

Allowed work-item statuses: `INTAKE`, `EVIDENCE_CAPTURED`, `TRIAGE_PROPOSED`, `APPROVAL_REQUIRED`, `APPROVED`, `STATUS_DRAFT`, `STATUS_APPROVED`, `CUSTOMER_RESPONDED`, `PAYMENT_PENDING`, `PAYMENT_CONFIRMED`, `PAYMENT_FAILED`, `OUTCOME_RECORDED`, `LEARNING_RECORDED`, `CLOSED`.

Every transition must validate the current state, write one `WorkItemEvent`, preserve `data_scope`, and commit atomically. Duplicate calls with the same idempotency key must return the existing record without duplicating events.

- [ ] **Step 4: Reuse existing `Evidence` and `EvidenceRelationship`.**

Create a new `Evidence` row with `provenance` and link it to the work item through the new work-item event metadata and an `EvidenceRelationship` relation key. Do not create a parallel evidence table.

- [ ] **Step 5: Reuse existing `Decision`, `Experiment`, and `execution_engine`.**

Create a `Decision` with status `proposed`, then create an `Experiment` action with `action_type="service_delivery"`, `execution_mode="requires_owner_action"`, `requires_owner_approval=True`, `domain="revenue"`, and `execution_allowed=False`. Call the existing approval boundary; never call the existing `start_action` as an autonomous customer contact or payment executor.

- [ ] **Step 6: Implement communication as reviewed state only.**

`propose_customer_status` creates `DRAFT`. Approval changes it to `APPROVED`; no external delivery occurs. A future explicit send action may create an `IntegrationDelivery`, but this P1 slice does not send automatically.

- [ ] **Step 7: Implement payment truth boundary.**

Manual payment confirmation requires provider/reference evidence and creates an `Outcome` with `outcome_type="ACTUAL_REVENUE"`, `verification_state="VERIFIED"`, and explicit `data_scope`. A rejected/failed payment creates no actual-revenue outcome. Customer acceptance alone cannot confirm payment.

- [ ] **Step 8: Implement outcome and learning recording.**

Create an `Outcome` first, then a linked `LearningEvent` comparing the triage expectation with the actual result. Only `REAL` verified outcomes may update product rollups; `SANDBOX` outcomes remain excluded by existing product-engine logic.

- [ ] **Step 9: Run focused service tests.**

Run: `cd backend && python3 -m pytest tests/test_repair_shop_service.py -q`

Expected: PASS.

---

### Task 3: Add API routes and typed contracts

**Files:**
- Create: `backend/app/api/repair_shop.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_repair_shop_api.py`

**Interfaces:**
- `POST /repair-shop/work-items` creates a customer and work item.
- `GET /repair-shop/work-items` lists work items by `data_scope`.
- `GET /repair-shop/work-items/{id}` returns the complete audit detail.
- `POST /repair-shop/work-items/{id}/evidence` attaches evidence.
- `POST /repair-shop/work-items/{id}/triage` creates a proposed decision/action.
- `POST /repair-shop/communications/{id}/approve` approves a draft without sending it.
- `POST /repair-shop/communications/{id}/response` records customer acceptance/rejection.
- `POST /repair-shop/work-items/{id}/payment` records only verified manual/provider payment evidence.
- `POST /repair-shop/work-items/{id}/outcome` records outcome and learning.

- [ ] **Step 1: Write failing API tests.**

Test valid creation, missing required fields, evidence linkage, triage requiring approval, communication remaining unsent, failed payment not creating revenue, duplicate idempotency, and SANDBOX isolation.

- [ ] **Step 2: Register schemas and router, then run the tests to confirm expected failures become route-level failures only.**

Run: `cd backend && python3 -m pytest tests/test_repair_shop_api.py -q`

- [ ] **Step 3: Add strict Pydantic request/response schemas.**

Use bounded string lengths, explicit `Literal` states, nonnegative finite payment amounts, required consent state, and `data_scope: Literal["REAL", "SANDBOX"]` defaulting to `SANDBOX` for test-facing creation.

- [ ] **Step 4: Add the router to `main.py`.**

Keep the existing API-key middleware for mutating routes. Do not introduce a second authentication/session system.

- [ ] **Step 5: Implement route handlers as thin service calls.**

Do not embed business state transitions in route handlers. Return `409` for invalid transitions, `404` for missing records, `422` for invalid payment evidence, and `200/201` only after a committed database operation.

- [ ] **Step 6: Run API tests and the full backend suite.**

Run: `cd backend && python3 -m pytest tests/test_repair_shop_api.py -q && python3 -m pytest tests/ -q`

Expected: focused tests pass and the existing suite remains green.

---

### Task 4: Add the minimum operating UI

**Files:**
- Create: `frontend/app/repair-shop/page.tsx`
- Modify: `frontend/components/Nav.tsx`
- Modify: `frontend/lib/api.ts`
- Test/build: existing frontend type-check and production build commands.

**Interfaces:**
- `api.listRepairWorkItems(scope)`
- `api.getRepairWorkItem(id)`
- `api.createRepairWorkItem(payload)`
- `api.attachRepairEvidence(id, payload)`
- `api.createRepairTriage(id, payload)`
- `api.approveCustomerCommunication(id)`
- `api.recordCustomerResponse(id, payload)`
- `api.recordRepairPayment(id, payload)`
- `api.recordRepairOutcome(id, payload)`

- [ ] **Step 1: Add typed client interfaces matching backend schemas.**

All nullable/unknown values render as `unknown`; no frontend estimate is treated as actual.

- [ ] **Step 2: Build a single `/repair-shop` page.**

The page must show work-item state, customer consent, evidence list, triage decision, approval state, communication state, payment state, outcome, learning event, and a clear REAL/SANDBOX badge. It must provide only the forms needed for intake, evidence, triage, response, manual payment confirmation, and outcome recording.

- [ ] **Step 3: Add the navigation link without redesigning existing pages.**

- [ ] **Step 4: Run TypeScript validation and production build.**

Run: `cd frontend && npx tsc --noEmit && npm run build`

Expected: zero type errors and successful production build, subject to available installed dependencies.

---

### Task 5: Run regression, database integrity, and browser smoke checks

**Files:**
- Create: `backend/tests/test_repair_shop_truth_controls.py`
- Create: `verification/repair-shop-p1-tests.txt`
- Create: `verification/repair-shop-p1-integrity.txt`
- Create: `verification/repair-shop-p1-browser-smoke.txt`

- [ ] **Step 1: Add explicit truth-control tests.**

```python
def test_unapproved_action_cannot_execute(db): ...
def test_failed_payment_cannot_be_actual_revenue(db): ...
def test_customer_acceptance_is_not_payment(db): ...
def test_payment_is_not_successful_outcome(db): ...
def test_sandbox_revenue_does_not_roll_up(db): ...
def test_duplicate_submission_is_idempotent(db): ...
```

- [ ] **Step 2: Run all backend tests and save the complete output.**

Run: `cd backend && python3 -m pytest tests/ -v > ../verification/repair-shop-p1-tests.txt`

- [ ] **Step 3: Check schema and historical truth.**

Verify table creation, foreign-key checks, signal count, existing actual revenue, product rollups, and no deleted/rewritten historical rows. Save results to `verification/repair-shop-p1-integrity.txt`.

- [ ] **Step 4: Run frontend type-check and build.**

Append output to the verification record.

- [ ] **Step 5: Run a local API smoke test with SANDBOX data only.**

Create one labeled SANDBOX work item, move it through intake/evidence/triage/approval/communication/payment-failure/outcome, verify no real revenue changes, and remove no historical data. Save the response sequence.

- [ ] **Step 6: Run browser smoke verification if a local server is safely available.**

Open `/repair-shop`, verify the state and scope labels are visible, and record the result. Do not send a customer message or create a REAL payment.

---

### Task 6: Prepare the one real-world experiment without executing external contact

**Files:**
- Create: `docs/REPAIR_SHOP_FIRST_EXPERIMENT.md`
- Modify: `docs/OPERATOR_GUIDE.md` only if required to link the procedure.

- [ ] **Step 1: Document exactly one hypothesis.**

Hypothesis: an independent repair shop will pay a small fixed amount for one completed workflow because it reduces intake/follow-up time or improves customer communication.

- [ ] **Step 2: Define customer, problem, offer, price, metric, stop condition, and evidence.**

Initial price proposal: NPR 100 for one completed workflow, subject to owner approval and local market discussion. This is a proposed price, not revenue.

- [ ] **Step 3: Document the pilot procedure.**

One real shop, one real problem, one real work item, explicit consent, manual fallback, reviewed customer communication, verified payment evidence, linked outcome, and learning record.

- [ ] **Step 4: State what still prevents the first dollar.**

No real repair shop, customer, payment, or outcome has yet been recorded. No external communication is executed by this implementation without explicit operator action.

---

## Verification checklist

- [ ] No Assignment-5 or legacy mirror file changed.
- [ ] No old credential, dependency, upload, session, or authentication code imported.
- [ ] No duplicate execution, experiment, revenue, or learning system created.
- [ ] Existing backend tests pass.
- [ ] Frontend type-check and build pass.
- [ ] Database integrity and historical counts remain unchanged.
- [ ] Actual revenue remains `$0` until verified real payment evidence is entered.
- [ ] Browser smoke test shows clear state and REAL/SANDBOX labels.
- [ ] First experiment document is prepared but no customer is contacted automatically.
