# Repair-Shop First Experiment

## Hypothesis

An independent repair shop will pay a small fixed amount for one completed ForgeOS-assisted workflow because a structured intake, reviewed status update, and recorded outcome reduce intake or follow-up friction. This is a **hypothesis**, not a verified market claim.

## One-work-item pilot

The operator should select one real shop and one real repair problem. The customer must give the consent required for the chosen contact channel. The operator records the asset, the reported problem, and the observed evidence in **REAL** scope. The operator then reviews the proposed triage decision and approves the human work item. ForgeOS does not call, message, diagnose, repair, or charge anyone automatically.

The initial price proposal is **NPR 100 for one completed workflow**. This is an estimate and proposed offer, not revenue. The primary metric is whether the shop completes and pays for one workflow; the secondary metric is the operator's observed time or follow-up burden compared with the unstructured baseline. A stop condition is any false claim of payment, missing customer consent, inability to verify the work item, or customer rejection that makes continuation inappropriate.

## Evidence and truth boundaries

The operator records the real response separately from payment. Customer acceptance is not payment. A payment is recorded as `ACTUAL_REVENUE` only after a verified provider reference or equivalent manual payment evidence is entered. A payment is not a successful service outcome; the operator must separately record what actually happened. The resulting `Outcome` and `LearningEvent` are linked to the existing ForgeOS experiment/action and remain visible as **REAL** or **SANDBOX** according to the selected scope.

If payment fails or cannot be verified, no actual-revenue outcome is created. If the exercise is rehearsed, it must use a separate sandbox database and remain visibly labeled `SANDBOX`; it must not alter the real commercial baseline.

## What still prevents the first dollar

No real repair shop, customer, payment, or successful repair outcome has been recorded by this document. The application is prepared for one operator-led experiment, but a human still needs to identify the shop, obtain consent, perform or coordinate the actual work, communicate manually, collect money, and enter genuine evidence. No customer contact is automated by this vertical slice.
