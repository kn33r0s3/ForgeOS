# FORGEOS PHASE 5 — EVIDENCE CAPTURE READINESS REPORT

**Document Location**: `ForgeOS/PHASE_5_EVIDENCE_CAPTURE_READINESS.md`  
**Target Opportunity**: Opportunity #7 — Automated Appointment Status Notifications for Repair Shops  
**Execution Mode**: SCHEMATIC & API AUDIT FOR REAL EVIDENCE INGESTION (Zero DB mutations, zero fake customers)  

---

## A. EXISTING SCHEMA AUDIT

ForgeOS's relational database contains five interconnected models capable of tracking real-world customer discovery evidence:

1. **`models.Signal`** (Raw Observation Ingestion):
   * `id` (INTEGER PRIMARY KEY)
   * `source` (VARCHAR) — e.g. `'manual'`, `'phone_interview'`
   * `source_type` (VARCHAR) — `'manual'` (human operator input)
   * `content` (TEXT) — Verbatim raw transcript / customer notes
   * `canonical_url` (VARCHAR) — Public business website URL
   * `retrieved_at` (DATETIME) — UTC timestamp of conversation
   * `provenance` (TEXT) — Structured metadata (contact person, method, location)

2. **`models.Evidence`** (Structured Evidence Linkage):
   * `id` (INTEGER PRIMARY KEY)
   * `opportunity_id` (INTEGER FK) — References Opportunity #7
   * `signal_id` (INTEGER FK) — References the raw Signal record
   * `source` (VARCHAR) — `'customer_interview'`
   * `content` (TEXT) — Summary of customer statements
   * `direction` (VARCHAR) — `'supporting'`, `'refuting'`, or `'neutral'`
   * `confidence` (FLOAT) — Initial weighting of response validity
   * `canonical_url` (VARCHAR) — Prospect website URL
   * `provenance` (TEXT) — Audit details of contact

3. **`models.Experiment`** (Validation Action Tracking):
   * `id` (INTEGER PRIMARY KEY)
   * `opportunity_id` (INTEGER FK) — References Opportunity #7
   * `action_type` (VARCHAR) — `'customer_interview'`
   * `hypothesis` (TEXT) — Specific statement tested
   * `status` (VARCHAR) — `'planned'`, `'in_progress'`, `'completed'`, `'abandoned'`
   * `result` (TEXT) — Documented conversation outcome
   * `lesson` (TEXT) — Key takeaway / learning
   * `conversions` (INTEGER) — `1` if interest/trial requested, `0` if not
   * `revenue` (FLOAT) — `0.0` for discovery stage
   * `required_inputs` (TEXT) — Prospect business name and phone number
   * `execution_mode` (VARCHAR) — `'requires_owner_action'`
   * `data_scope` (VARCHAR) — `'REAL'`

4. **`models.Decision`** (Strategic Action Context):
   * `id` (INTEGER PRIMARY KEY)
   * `opportunity_id` (INTEGER FK) — References Opportunity #7 (Decision #7)
   * `title` (VARCHAR) — Action rationale title
   * `status` (VARCHAR) — `'accepted'`
   * `rationale` (TEXT) — Why outreach was selected

5. **`models.OpportunityEvent`** (Append-Only Audit History):
   * `id` (INTEGER PRIMARY KEY)
   * `opportunity_id` (INTEGER FK) — References Opportunity #7
   * `event_type` (VARCHAR) — `'customer_interview_completed'` or `'evidence_added'`
   * `event_key` (VARCHAR) — Unique event identifier
   * `details` (TEXT) — JSON string containing full prospect metadata and response metrics

---

## B. EXISTING CREATION APIS & SERVICE CODE PATHS

Real evidence collected from a human customer conversation can be ingested into ForgeOS using existing backend service methods and API endpoints:

1. **Raw Signal Ingestion (`app/services/observer_engine.py`)**:
   ```python
   obs = ObserverEngine(db)
   sig = obs.observe(
       content=raw_transcript_notes,
       source="manual",
       metadata={
           "source_type": "manual",
           "canonical_url": prospect_website_url,
           "provenance": json.dumps({
               "prospect_name": business_name,
               "contact_person": contact_person,
               "contact_method": contact_method,
               "timestamp": conversation_timestamp,
           }),
       }
   )
   ```

2. **Structured Evidence Linking (`app/services/money_engine.py`)**:
   ```python
   ev = models.Evidence(
       opportunity_id=7,
       signal_id=sig.id,
       source="customer_interview",
       content=summary_of_findings,
       direction="supporting",  # or "refuting" or "neutral"
       confidence=80.0,
       canonical_url=prospect_website_url,
       provenance=sig.provenance
   )
   db.add(ev)
   ```

3. **Experiment Completion (`app/services/execution_engine.py`)**:
   ```python
   # Complete Experiment attached to Opportunity #7
   exp = db.query(models.Experiment).filter_by(opportunity_id=7, action_type="customer_interview").first()
   exp.status = "completed"
   exp.completed_at = datetime.now(timezone.utc)
   exp.result = outcome_summary
   exp.lesson = key_learnings
   exp.conversions = 1 if trial_requested else 0
   ```

---

## C. EXACT FIELDS AVAILABLE FOR MAPPING

The following required information points map directly onto existing schema columns:

| Information Point | Target Model | Target Field |
| :--- | :--- | :--- |
| Business Name | `models.Signal` / `models.Evidence` | `provenance` (JSON string) |
| Person Contacted | `models.Signal` / `models.Evidence` | `provenance` (JSON string) |
| Date / Time | `models.Signal` / `models.Evidence` | `timestamp` / `retrieved_at` / `created_at` |
| Contact Method | `models.Signal` / `models.Evidence` | `source` (`'phone_call'`, `'email'`) / `provenance` |
| Raw Customer Statement | `models.Signal` | `content` (TEXT) |
| Source URL | `models.Signal` / `models.Evidence` | `canonical_url` (VARCHAR) |
| Linked Hypothesis | `models.Experiment` | `hypothesis` (TEXT) |
| Evidence Direction | `models.Evidence` | `direction` (`'supporting'`, `'refuting'`, `'neutral'`) |
| Experiment Association | `models.Evidence` / `models.Experiment` | `opportunity_id` / `experiment_id` |
| Opportunity Association | `models.Opportunity` | `id` (`7`) |

---

## D. SCHEMA SUFFICIENCY VERIFICATION

* **Schema Gap Check**: **ZERO GAPS IDENTIFIED**.
* **Conclusion**: Existing database models (`Signal`, `Evidence`, `Experiment`, `OpportunityEvent`, `Opportunity`) are 100% sufficient to capture real customer discovery conversations without any schema migrations, new tables, or code alterations.

---

## E. PROPOSED MINIMAL CHANGE

* **No DDL schema changes are required.**
* **No table creation is required.**

---

## F. CONCRETE RECORDING EXAMPLE (EXAMPLE ONLY)

*Note: The following is an **EXAMPLE ONLY** demonstrating how a future genuine conversation will be stored in SQLite once executed by the human operator. NO fake customer records have been created in `storage/forge.db`.*

### Example Code Snippet for Future Ingestion
```python
# EXAMPLE CODE PATH — FOR FUTURE EXECUTION WHEN REAL NOTES ARE PROVIDED
from datetime import datetime, timezone
import json
from app.services.observer_engine import ObserverEngine
from app import models

def record_real_customer_interview(db, prospect_data):
    """
    Ingests one genuine real-world customer discovery interview.
    prospect_data format:
    {
        "business_name": "Auto Tek",
        "person_contacted": "Shop Manager",
        "contact_method": "phone_call",
        "website_url": "https://www.autotekinc.net",
        "raw_notes": "Manager stated front desk receives ~15 calls daily asking 'is my car ready?'...",
        "software_used": "Mitchell1",
        "has_automated_sms": False,
        "direction": "supporting", # "supporting" | "refuting" | "neutral"
        "trial_requested": True,
        "timestamp": "2026-09-23T10:30:00Z"
    }
    """
    # 1. Ingest raw transcript into signals
    obs = ObserverEngine(db)
    prov_str = json.dumps({
        "business_name": prospect_data["business_name"],
        "person_contacted": prospect_data["person_contacted"],
        "contact_method": prospect_data["contact_method"],
        "software_used": prospect_data["software_used"],
        "has_automated_sms": prospect_data["has_automated_sms"],
        "timestamp": prospect_data["timestamp"]
    })
    
    sig = obs.observe(
        content=prospect_data["raw_notes"],
        source=prospect_data["contact_method"],
        metadata={
            "source_type": "manual",
            "canonical_url": prospect_data["website_url"],
            "provenance": prov_str
        }
    )
    
    # 2. Link structured Evidence to Opportunity #7
    ev = models.Evidence(
        opportunity_id=7,
        signal_id=sig.id,
        source="customer_interview",
        content=f"Interview with {prospect_data['business_name']}: {prospect_data['raw_notes'][:200]}",
        direction=prospect_data["direction"],
        confidence=80.0,
        canonical_url=prospect_data["website_url"],
        provenance=prov_str
    )
    db.add(ev)
    
    # 3. Log OpportunityEvent audit record
    evt = models.OpportunityEvent(
        opportunity_id=7,
        event_type="customer_interview_completed",
        event_key=f"interview:{sig.id}",
        details=prov_str
    )
    db.add(evt)
    db.commit()
```

---

**STOPPING HERE.** Phase 5 Evidence Capture Readiness Report complete and saved to [`ForgeOS/PHASE_5_EVIDENCE_CAPTURE_READINESS.md`](file:///Users/nirojpaudyal/Downloads/ForgeOS/PHASE_5_EVIDENCE_CAPTURE_READINESS.md). Ready to ingest real customer notes when provided.
