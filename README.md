# Current personal pilot checkpoint — September 14, 2026

**REAL revenue: $0. REAL customers: 0. External validation: 0.**
The current startup and human workflow instructions are in [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md).
Architecture map: [docs/FINAL_ARCHITECTURE.md](docs/FINAL_ARCHITECTURE.md).
Verified release results: [STATUS.md](STATUS.md) and [COMPLETION_REPORT.md](COMPLETION_REPORT.md).
Older roadmap/readiness statements below are historical, not verified sales claims.
Use a separate database for synthetic source inputs, plus SANDBOX labels downstream.

---

# ForgeOS

**Continuously improving intelligence + execution system.**  
Grounded in reality. Offline-capable. $0 by default.

---

## What ForgeOS is

ForgeOS is not a scoring SaaS and not a leaderboard of business ideas.

It is a system organized around:

```
OBSERVE → VERIFY → UNDERSTAND → DECIDE → ACT → MEASURE → LEARN → repeat
```

Intelligence emerges from the full evidence → reasoning → decision → action → outcome → learning loop — not from an LLM or a heuristic score alone.

---

## Core domain model

Observation → Evidence → Pattern → Hypothesis/Belief → Opportunity  
→ Decision → Strategy → Action → Experiment → Outcome → Measurement → Learning  
→ Belief/strategy update

Every important claim can answer:
- What do we know?
- What do we think?
- How do we know?
- What contradicts it?
- What don’t we know?
- What should we do to find out?

Knowledge is labeled: **OBSERVED / INFERRED / ESTIMATED / UNKNOWN / ACTUAL**.

---

## Quick Start

```bash
chmod +x start.sh stop.sh
./start.sh          # Mac/Linux
# or
.\start.ps1         # Windows
```

- Dashboard: http://localhost:3000  
- API docs:  http://localhost:8000/docs  
- Worker: disabled by default; enable deliberately with `FORGEOS_ENABLE_WORKER=true ./start.sh`  

Stop: `./stop.sh`

---

## Architecture (backend)

| Layer | Role |
|-------|------|
| Observer + Collectors | Normalized observations with provenance |
| Signal quality | Concreteness, coherence, duplication gates |
| Pattern engine | Repeated problems from real signals |
| Belief + Evidence | Hypotheses with supporting/contradicting evidence |
| Reality checker / memory | Confidence drift, predictions, source reliability |
| Opportunity engine | Downstream of evidence; heuristic scores labeled as such |
| Economic intelligence | ESTIMATED vs ACTUAL revenue/cost separation |
| Decision engine | Explicit rationale, alternatives, expected outcomes |
| Autonomy / policy | ALLOW / REQUIRE_APPROVAL / BLOCK |
| Execution engine | Action lifecycle (never silent success) |
| Experiment runners | Belief tests + opportunity tests |
| Learning engine | Expected vs actual → structured LearningEvents → belief updates |
| Forge loop + worker | Full cycle orchestration |

NEPSE / paper trading / stock prediction: **removed and not restored**.

---

## Manual Analyze flow

Input: *“Restaurants still take orders on paper.”*

Output is structured intelligence, not only scores:
- Observation stored (user report, provenance)
- Opportunity with **HEURISTIC** score
- Explicit unknowns (willingness to pay, market size, …)
- Recommended next experiment
- Proposed Decision for low-cost validation

---

## Tests

```bash
cd backend
python3 -m pip install --target .deps -r requirements.txt
PYTHONPATH="$PWD/.deps:$PWD" python3 -m pytest tests/ -q
```

Includes a full end-to-end intelligence loop test:
observation → evidence → pattern → belief → opportunity → decision → experiment → learning.

---

## Philosophy

- No fake certainty
- No conflating estimates with actuals
- LLM is a reasoning component, not the database of truth
- Policy gates all consequential actions
- Progressive improvement through contact with reality
