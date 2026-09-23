# CURRENT_FOCUS.md — Nepal-First Real Result

**Last updated**: 2026-09-14  
**Status**: Software workflow complete and verified locally; one real-person pilot remains the external gate.

## Single Goal

Get **one real Nepali user** through one safe earning experiment with evidence:

```
Real person (14+)
→ real offer
→ real customer conversation
→ delivery or clear refusal
→ verified payment OR honest zero
→ outcome recorded in ForgeOS
```

## What Already Exists

- `/earn` workspace (Nepali + English)
- 5 earning pathways
- Age gate 14+ with safety copy for 14–17
- Offline offer drafting (localStorage)
- Clear labeling: draft = hypothesis, not revenue
- Payment provider plan (eSewa, Khalti, Fonepay) — credentials not yet live
- Durable integration outbox pattern in architecture

## Highest-Leverage Next Steps (in order)

1. Make the Earn workspace support honest status progression:
   - draft → customer_confirmed → paid / failed / abandoned
2. Add a simple “next real action” checklist per offer so a human knows exactly what to do offline.
3. Run one pilot with a real person (not simulated).
4. Only after one verified payment or clear negative result, expand pathways or connect live payment credentials.

## Explicitly Forbidden Until One Real Outcome

- Claiming income guarantees
- Treating drafts as customers or revenue
- Collecting OTP, PIN, citizenship numbers, or wallet secrets
- Mass unsolicited outreach tools
- Expanding to many pathways before one pathway works end-to-end

## Success Criteria (this phase)

- [x] User can save an offer and advance its status honestly
- [x] Each offer shows a concrete next real-world action
- [ ] One real person completes the loop (even if result is “no sale”)
- [ ] Outcome is recorded without fake revenue

Parent company direction remains open (Aether Group / Apex). First product experiments stay Nepal-first and truth-first.
