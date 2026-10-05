# HAMI CONTINUITY LAW

There is only one Hami.

Hami begins at commit 07baf91a1900cf3e27ce0bae9fead126801da3b3 (tagged `hami-origin`).
All later work is an in-place evolution of that same system.

Never create a second Hami, parallel architecture, replacement subsystem,
versioned duplicate, or competing canonical implementation merely because
the requested capability is new.

Before coding:
1. Find the existing seam that already carries the requested meaning.
2. Trace its history with git (`git log --follow`, `git blame`, `git log -S`).
3. Modify that seam in place when possible.
4. Reuse existing primitives, events, evidence, authorization, state,
   routes, components, services, and tests.
5. Treat new files as exceptional and justify why an existing seam cannot
   carry the behavior.

A request is not permission to add architecture.

Tests are contracts and evidence, not targets.
Do not alter production behavior solely to satisfy stale tests.

When historical implementations conflict:
recover the valuable behavior and integrate it into the existing Hami
lineage rather than selecting or creating another version.

Never delete history, reset to a convenient version, force-push,
delete recovery branches, or discard reachable historical work during
recovery.

The repository itself is the memory of Hami.

---

## HARD MECHANICAL RULE: NEW FILES

For every new file, the agent must first identify the existing file/function/model
that carries the same meaning and explain why modification is insufficient.
No explanation = no new file.

Before creating ANY new file, the agent must demonstrate in the commit message or PR description:
1. EXISTING SEAM INSPECTED: <file:function/component/model>
2. WHY IT CANNOT BE MODIFIED: <specific technical reason>
3. WHAT GENUINELY NEW CAPABILITY REQUIRES THE FILE: <specific capability>

If this cannot be proven, do not create the file. Modify existing code instead.

---

# FORGEOS TOP RULE — DRIVE OWNER DEPENDENCY TO ZERO

This is Hami's first substantive project rule: prefer fewer owner actions per
real economic outcome, while keeping authorization, evidence, privacy, legal,
and platform boundaries intact. Do not mistake more infrastructure, synthetic
activity, or a policy `ALLOW` for economic autonomy.

**Commercial focus:** one real customer → one real paid outcome → repeat →
automate → scale. Hami is the existing ForgeOS system evolving in place, not a
second architecture. The first pilot must be outcome-oriented and grounded in
owner-run discovery; do not assume a category, price, willingness to pay, or
public offer. The $249 Hami Revenue Operator is a later-stage offer only after
demonstrated value, not a bootstrap product to sell now.
The Nepal education-abroad and foreign-employment consultancy segments remain
hypotheses until the owner reports the five real conversations. Work only with
licensed agencies if those conversations support the segment; foreign
employment requires additional regulatory and reputation review.

**Bootstrap rule:** no new paid software or infrastructure before first real
customer revenue, except a verified legal, security, payment, or
critical-execution requirement. Forge Bot runs natively in ForgeOS; n8n is not
a dependency. Never contact a person, publish an offer, spend money, or
simulate prospect conversations without explicit owner authorization. Keep
`REAL`, `TEST`, `MOCK`, and `HYPOTHESIS` evidence distinct; tests never count as
customer or revenue evidence.

**Market-research rule:** do not frame another company, startup, marketplace,
or product as Hami's competition, and do not build competitor rankings or
"beat X" features. Study existing systems only for factual market context,
available infrastructure, interoperability, user expectations, and
implementation lessons.

Before each change, identify from code or runtime evidence: (1) the routine
owner action still required, (2) the action this change removes, (3) what
remains and what permission or infrastructure blocks it, and (4) the next
removable dependency. Record the current blocker and verification in the
existing `docs/CAPABILITY_QUEUE.md` ledger. Do not introduce another ledger or
canonical domain primitive.

Measure `OWNER_INTERVENTIONS_PER_REAL_TRANSACTION` only from verified real
transactions. If there are no such transactions, report the metric as
**NOT MEASURABLE**, never as zero. A seam is not autonomous until its production
path executes under explicit standing authorization without routine owner
interaction. Standing authorization may remove repeated approvals only within
its recorded action, purpose, scope, spend, rate, privacy, counterparty,
exclusion, expiry, and evidence limits; it never supplies missing external
permission or execution capability.
