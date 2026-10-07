# Decisions (what I chose and why)

## Rules I read (AGENTS.md, in my own words)

1. ForgeOS exists to drive owner dependency to zero: fewer owner actions per REAL economic outcome, while keeping authorization, evidence, privacy, legal, and platform boundaries intact. More infrastructure or synthetic activity is not autonomy.
2. No paid software or infrastructure before the first real customer revenue, except a verified legal, security, payment, or critical-execution requirement.
3. Never contact a person, publish an offer, spend money, or simulate prospect conversations without the owner's explicit authorization.
4. REAL, TEST, MOCK, and HYPOTHESIS must never be mixed. Tests never count as customer or revenue evidence, and OWNER_INTERVENTIONS_PER_REAL_TRANSACTION is NOT MEASURABLE until a real transaction is verified — never zero.

## README loop (in my own words)

OBSERVE → VERIFY → UNDERSTAND → DECIDE → ACT → MEASURE → LEARN → repeat.
Intelligence comes from the full evidence-to-learning loop, not from any single
model or score. Tests never count as customer evidence.

## Renovation working notes

- 2026-10-08: Executing the renovation playbook (Phases 0–4) as working
  discipline in a fresh worktree of origin/main. The playbook's
  `git checkout -b renovation` step is SKIPPED per the owner's standing
  direct-to-main rule (no branches, always); work happens directly on the
  worktree HEAD and pushes HEAD:main. The `pre-renovation` tag is kept as
  the rollback bookmark.
- 2026-10-08: docs/RENOVATION/HAMI_AGENT_PLAYBOOK.txt and playbook_cli.py
  do not exist in this repo (verified by listing docs/RENOVATION after
  creation). Noted in OWNER_QUESTIONS.md; the playbook content lives in
  the agent's context instead. Not creating them: nothing in the repo
  references them.
- 2026-10-08: The playbook's suggested owner question "AGENTS.md mixes
  ForgeOS rules with an App Builder sandbox contract — should they be
  split?" is FALSE. Verified: zero mentions of "app builder" in AGENTS.md
  (case-insensitive grep). No question written; recording the correction
  here instead.
- 2026-10-08: The playbook's "TEN STOP SIGNS" are not present in the
  provided source, so docs/RENOVATION/HAMI_RULES.md is not created from
  them. The four rules above plus the standing doctrine serve instead.
