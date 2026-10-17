# Hami Human-First Product Standard

**Purpose:** Make Hami's public website and every user-facing interaction comprehensive in meaning, natural to read, and simple to use. Hami's internal complexity must not become the public's burden.

## The first question is the person

Every public page and ForgeBot interaction should answer, in ordinary language:

1. Who is this for?
2. What real problem or need does it address?
3. What can Hami actually do to help today?
4. What does the person need to do next, if anything?
5. What will it cost—in money, time, effort, information, or risk?
6. What is known, what is uncertain, and what has actually happened?
7. How can the person correct us, decline, or leave?

If a page cannot answer these clearly, simplify it before adding more features.

## Public language rules

- Use short, concrete sentences and familiar words. Explain necessary technical terms immediately.
- Prefer people's goals and outcomes over system architecture, model names, internal scores, and workflow labels.
- Use natural English and Nepali where useful; Nepali must be meaningful and reviewed, not decorative machine-translated filler.
- Give examples that a real person can recognize. Do not invent testimonials, customers, demand, partnerships, savings, revenue, or success stories.
- Never use a polished interface to imply that an unfinished capability works.
- Keep detailed technical explanations available for people who want them, but do not make them prerequisites for ordinary use.
- Make pages readable on a phone, with clear headings, accessible controls, visible errors, and one obvious next step.

## Homepage contract

A first-time visitor should quickly understand:

- **What Hami is:** a system built to understand real needs and help turn them into useful outcomes.
- **Who it serves:** people, businesses, and communities; its Nepal roots do not limit whom it can serve.
- **What it does:** learns about needs, connects relevant knowledge and capabilities, and helps move useful work toward action.
- **What is real today:** current working capabilities and limitations, without inflated claims.
- **How to engage:** one clear, honest next step. Do not imply a public contact or intake channel is open if it is closed.

The homepage should not force visitors to understand the internal research loop, six data primitives, source adapters, experiments, or owner operations before they understand the human purpose. Technical details belong on appropriate supporting pages.

## Navigation and page design

- Organize the first-level navigation around visitor intentions, not internal subsystems.
- Keep the primary choices few and distinct. Move specialist records, technical details, and owner operations deeper without deleting useful capabilities.
- Each page should have one primary purpose and one clear next step.
- Avoid duplicate pages, competing labels, unexplained acronyms, empty dashboards, and long lists that make visitors do Hami's sorting work.
- Do not expose owner-only, test-only, or closed actions as if they were available public services.
- Empty states must explain what is missing and what the visitor can do; never fill gaps with sample records presented as real.

## Trust and evidence

Label the difference between:
- **Available now:** implemented and currently accessible.
- **In progress:** being built or connected.
- **Not yet verified:** not demonstrated reliably in the real world.
- **Confirmed result:** supported by appropriate evidence of what actually happened.

A test passing is not a customer result. A published offer is not a sale. A payment is not proof that promised work was fulfilled. A research signal is not proof of a person's need. Never claim otherwise.

## Human-value review before shipping

For each change, record:
- The specific human problem it improves.
- The person or group who benefits, without assuming their needs.
- The effort, delay, confusion, or risk removed.
- The new burden or risk introduced.
- The evidence needed to tell whether it helped.
- The simplest way to explain the change to a nontechnical person.

Prefer a smaller, understandable improvement that helps a real person over a larger feature that mainly increases internal complexity.

## Immediate review targets

The current homepage at `src/routes/index.tsx` uses the headline “Discover what matters. Understand it. Act on it.” and introduces Hami as a system that turns understanding into real value. That is directionally aligned, but the surrounding page also exposes internal capability labels and a technical “reality loop.” Review whether a first-time visitor can understand the practical benefit before encountering those concepts.

The canonical navigation in `src/lib/hami-system.ts` currently lists Home, Findings, Unknowns, Network, Experiments, Services, Group, and About. Review this against real visitor intentions and consolidate the first-level choices only when route coverage, accessibility, and existing tests are preserved. Keep specialist pages available; simplicity is not deletion.

## Definition of success

A person unfamiliar with Hami should be able to explain what it is, whether it can help them, what happens next, and what is not yet proven—without assistance from the builder. The ultimate measure is not fewer words or a prettier site; it is less confusion and more verified benefit for people.
