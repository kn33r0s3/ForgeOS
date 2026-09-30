# BLUEPRINT AMENDMENT CANDIDATE — BAC-001: The personal System is the primary view

Status: candidate. Not merged into `FORGE_SUBSTRATE_BLUEPRINT.md`; the owner reconciles it.

## Discovered principle

The primary product surface is a projection of **one person's real-world
situation** (their gear: location, time, capabilities, resources, goals,
constraints) joined to **changing world state**. Posts, boards, and request
intake are mechanisms inside that view. They are not the view.

## Evidence

- On 2026-09-29 the public home drifted to "Browse or post work / Share a need",
  with the work board first in navigation (commits `ea562b8`..`de7c070`).
- In production (2026-09-30): `/api/public/domain` = `[]`, `/matches` = `[]`,
  `/providers` = `[]`. A board-first home therefore shows empty boards to every
  visitor. The same visitor's own gear always carries information: paths can
  be derived from it truthfully with no external supply.

## Affected subsystems

Public web (home, nav), Feed (becomes the "what changed" panel of a System),
Network (future traversal starting at the person), matching, progression.

## Why it matters

It turns "nothing here yet" into "here is what your own situation makes
possible". It keeps every truth boundary intact, and it lets continuous
discovery attach to a person rather than to anonymous posts.

## Proposed wording

> Hami's primary interface is the person's System: a projection of their
> stated, inferred, and evidenced situation joined to changing public world
> state. Boards, forms, and feeds are mechanisms inside it. A System view
> must label provenance on every personal fact, keep derived paths at
> `possible` until tested, and gate outcome stages on verified evidence.

## Compatibility with the six primitives

Full. Person = ENTITY; capability/resource = CAPABILITY + RELATION (`has`,
`can_do`); goal/constraint = ENTITY attributes with provenance; path =
hypothesized RELATION at `possible`; step taken = ACTION; result = EVENT +
EVIDENCE. No new top-level ontology.

## Implementation consequence

1. Now (done): client-local System state with `stated` provenance only.
2. Next: consented server persistence through canonical writers (identity
   `candidate`, not merged). This enables per-person continuous discovery
   and a "since you were away" delta.
3. Later: verified evidence (completed work, verified payment) promotes
   progression stages server-side only.
