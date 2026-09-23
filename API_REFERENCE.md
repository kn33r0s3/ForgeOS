# ForgeOS API Reference

**Base URL:** `http://localhost:3000/api` or `http://localhost:8000`  
**Documentation:** http://localhost:8000/docs (interactive Swagger UI)

---

## Health & Status

### GET /health
Check if backend is running.
```bash
curl http://localhost:3000/api/health
```
Response:
```json
{"status": "ok"}
```

### GET /ai/status
Check AI provider status.
```bash
curl http://localhost:3000/api/ai/status
```
Response:
```json
{
  "provider": "ollama",
  "status": "READY",
  "note": "Real provider configured."
}
```

---

## Signals (Observations)

### GET /signals
Get all raw signals/observations.
```bash
# All signals
curl http://localhost:3000/api/signals

# Format nicely
curl http://localhost:3000/api/signals | jq '.[0:3]'

# Get high-importance signals only
curl http://localhost:3000/api/signals | jq '.[] | select(.importance_score > 80)'

# Count by source
curl http://localhost:3000/api/signals | jq 'group_by(.source) | map({source: .[0].source, count: length})'
```

Response:
```json
[
  {
    "id": 11822,
    "source": "github",
    "content": "Small Businesses Marketing Blueprint...",
    "category": "customer support",
    "timestamp": "2026-09-11T16:01:54.828953",
    "signal_type": "demand",
    "importance_score": 75.0,
    "processed": true,
    "tags": "customer support,marketing,small business",
    "reliability_score": 95.0,
    "freshness_score": 100.0,
    "quality_score": 25.0,
    "quality_flags": "duplicate_of_signal_11742",
    "is_duplicate_of": 11742
  }
]
```

---

## Opportunities

### GET /opportunities
Get discovered business opportunities.
```bash
curl http://localhost:3000/api/opportunities | jq .

# High-confidence opportunities
curl http://localhost:3000/api/opportunities | jq '.[] | select(.confidence_score > 75)' | head -3

# Sorted by revenue potential
curl http://localhost:3000/api/opportunities | jq 'sort_by(.estimated_revenue) | reverse | .[0:5]'
```

Response:
```json
[
  {
    "id": 123,
    "title": "AI-powered customer support for small businesses",
    "description": "Small businesses struggle with customer support...",
    "confidence_score": 82.5,
    "estimated_revenue": 150000,
    "estimated_cost": 45000,
    "source_pattern_ids": [1, 2, 3],
    "evidence_signal_ids": [11822, 11821],
    "created_at": "2026-09-11T17:30:00",
    "status": "active"
  }
]
```

---

## Beliefs (Hypotheses)

### GET /beliefs
Get current hypotheses about the world.
```bash
curl http://localhost:3000/api/beliefs | jq .

# Only high-confidence beliefs
curl http://localhost:3000/api/beliefs | jq '.[] | select(.confidence_score > 70)'
```

Response:
```json
[
  {
    "id": 1,
    "statement": "Small businesses need better customer support tools",
    "confidence_score": 78.5,
    "sources": ["reddit", "github", "rss"],
    "supporting_evidence": 42,
    "contradicting_evidence": 3,
    "created_at": "2026-09-10T12:00:00",
    "updated_at": "2026-09-11T17:30:00"
  }
]
```

---

## Decisions & Execution

### GET /decisions
Get recommended actions.
```bash
curl http://localhost:3000/api/decisions | jq .
```

### GET /executions
Get outcomes of executed decisions.
```bash
curl http://localhost:3000/api/executions | jq '.[] | {id, decision_id, outcome, actual_cost, revenue_generated}'
```

---

## Workers & Tasks

### GET /workers
Get background worker task status.
```bash
# Active tasks
curl http://localhost:3000/api/workers | jq .

# Count by type
curl http://localhost:3000/api/workers | jq 'group_by(.worker_type) | map({type: .[0].worker_type, count: length})'

# Watch for changes (every 5 seconds)
watch -n 5 "curl -s http://localhost:3000/api/workers | jq 'length'"
```

Response:
```json
[
  {
    "worker_type": "opportunity",
    "task_name": "process_opportunities",
    "priority": 1,
    "inputs": {"task_results": []},
    "status": "completed"
  }
]
```

---

## Experiments & Learning

### GET /experiments
Get hypothesis tests.
```bash
curl http://localhost:3000/api/experiments | jq .

# Only completed experiments
curl http://localhost:3000/api/experiments | jq '.[] | select(.status == "completed")'
```

---

## Revenue & Economics

### GET /revenue
Get revenue sources and tracking.
```bash
curl http://localhost:3000/api/revenue | jq .

# Revenue by source
curl http://localhost:3000/api/revenue | jq 'group_by(.source) | map({source: .[0].source, total: map(.amount) | add})'
```

---

## Advanced Queries

### Count data by type
```bash
# Total signals
curl -s http://localhost:3000/api/signals | jq 'length'

# Total opportunities
curl -s http://localhost:3000/api/opportunities | jq 'length'

# Total beliefs
curl -s http://localhost:3000/api/beliefs | jq 'length'

# Dashboard stats
echo "=== ForgeOS Stats ===" && \
echo "Signals: $(curl -s http://localhost:3000/api/signals | jq 'length')" && \
echo "Opportunities: $(curl -s http://localhost:3000/api/opportunities | jq 'length')" && \
echo "Beliefs: $(curl -s http://localhost:3000/api/beliefs | jq 'length')" && \
echo "Workers: $(curl -s http://localhost:3000/api/workers | jq 'length')"
```

### Filter by date range
```bash
# Signals from today
curl -s http://localhost:3000/api/signals | jq '.[] | select(.timestamp > "2026-09-11T00:00:00")'

# Recent high-priority signals (last 1 hour, importance > 70)
curl -s http://localhost:3000/api/signals | jq '.[] | select(.timestamp > "2026-09-11T17:00:00" and .importance_score > 70)'
```

### Export to CSV
```bash
# Signals as CSV
curl -s http://localhost:3000/api/signals | jq -r '.[] | [.id, .source, .importance_score, .timestamp] | @csv' > signals.csv

# Opportunities as CSV
curl -s http://localhost:3000/api/opportunities | jq -r '.[] | [.id, .title, .confidence_score, .estimated_revenue] | @csv' > opportunities.csv
```

---

## Error Handling

Errors return appropriate HTTP status codes:
- `200` — Success
- `404` — Not found
- `500` — Server error

Example error response:
```json
{
  "detail": "Resource not found"
}
```

---

## Performance Tips

1. **Use jq for filtering** — Filter results locally to reduce payload:
   ```bash
   curl -s http://localhost:3000/api/signals | jq '.[] | select(.importance_score > 80)'
   ```

2. **Use pagination** (if supported) — Later versions may add `?limit=10&offset=0`

3. **Cache results** — Data doesn't change constantly:
   ```bash
   curl -s http://localhost:3000/api/opportunities > opportunities.json
   jq . opportunities.json  # Reuse local copy
   ```

4. **Use `-s` flag** — Suppress curl progress:
   ```bash
   curl -s http://localhost:3000/api/signals
   ```

---

## Real Examples

### Find all opportunities about "AI"
```bash
curl -s http://localhost:3000/api/opportunities | \
  jq '.[] | select(.title | contains("AI") or .description | contains("AI"))'
```

### Export high-confidence insights
```bash
curl -s http://localhost:3000/api/beliefs | \
  jq '.[] | select(.confidence_score > 75) | {statement, confidence_score, evidence_count}' > insights.json
```

### Monitor worker progress
```bash
while true; do
  echo "$(date '+%H:%M:%S') - Workers: $(curl -s http://localhost:3000/api/workers | jq 'length')"
  sleep 10
done
```

### Count signals by source
```bash
curl -s http://localhost:3000/api/signals | \
  jq -r '.[] | .source' | \
  sort | uniq -c | sort -rn
```

---

## Documentation

Full interactive API documentation: **http://localhost:8000/docs**

- Try endpoints directly in browser
- See all request/response formats
- Get schema information
- Execute real queries

