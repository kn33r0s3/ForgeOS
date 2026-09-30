# Canonical responsibility map

No new AI architecture. Existing FastAPI + Next.js + SQLite remain.

| Stage | Existing owner |
|---|---|
| Source input, normalization, quality, provenance | observer_engine, signal_processor, signal_quality, source_manager |
| Evidence / verification | observer _ensure_evidence, evidence services, reality_checker / reality_memory |
| Patterns / understanding / beliefs | pattern_engine, belief_engine, memory_layer |
| Problem and opportunity | opportunity_engine (pattern and strict single-signal discovery) |
| Economic extraction, score, confidence | economic_intelligence, money_engine |
| Decision rationale and feedback | decision_engine + lessons_engine.recall_lessons |
| Canonical composition | forge_loop stage 11.7 → orchestrator.run_orchestration_flow |
| Experiment and approval | execution_engine / autonomy_engine, existing Experiment model |
| Human external work | Human operator; no simulated customer agent |
| Actual response and measurement | orchestrator.record_demand_outcome → outcome_learning |
| Learning and durable memory | learning_engine → lessons_engine.consolidate_learning_event |
| Next decision | scoped decision_engine recommendation consuming persisted lessons |
| Controlled offer creation | orchestrator validation_counts / create_product_for_validated → product_engine |
| Distribution and contact ledger | product_engine, DistributionChannel, CustomerEvent |
| Collected money and learning again | action_engine.record_outcome → Outcome + product LearningEvent + Lesson |
| Direct legacy experiment cash | money_engine.record_revenue_result using same explicit Outcome ledger |
| Scheduling and recovery | cycle_scheduler → scripts.run_daily_cycle.run_once; backup.safe_backup |
| Human interface | frontend/app/flow/page.tsx, lib/api.ts; API /orchestrate /products /forge/outcomes |

GET Flow and product/channel summaries are read-only. Creation is explicit POST.
Outcome/learning/lesson/contact transaction is atomic. Stage-by-stage cycle commits
are recoverable but the whole discovery cycle is not atomic. Shared discovery data
requires a separate sandbox database. Decisions use existing title scope markers;
financial/product/experiment/learning records use existing data_scope fields.
Legacy Action API remains supported but is not the canonical interview unit.

Observed source text → signal/evidence → pattern/belief → opportunity/economic
score → scoped decision → approved human experiment → actual entered response →
measurement → learning/lesson → revised decision → validating offer → channel →
customer event → explicit cash → learning again.

The software records evidence and assumptions. It does not turn either into a
customer, independent market validation, fulfilled service, or bank payment.
