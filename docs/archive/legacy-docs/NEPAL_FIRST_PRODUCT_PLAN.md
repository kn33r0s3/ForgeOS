# ForgeOS Nepal-first product plan

## North star

ForgeOS should help people in Nepal aged **14 and above** turn a real skill, local need, or small business service into a safer path toward income. It must not promise that every person will profit. The product can provide opportunity discovery, skill-to-offer conversion, customer finding, workflow support, payment reconciliation, and reality-based learning; demand, legal eligibility, work quality, customer choice, and payment remain real-world conditions.

## Non-negotiable principles

ForgeOS is **offline-first and truth-first**. A person can create an offer, record a lead, draft a proposal, prepare a delivery checklist, and queue a payment or follow-up while disconnected. ForgeOS must never mark a payment complete from a client-side redirect, screenshot, model response, or queued request. A payment becomes actual revenue only after provider-side verification and an idempotent ledger entry.

Every result is labeled as one of **raw, observed, inferred, human-validated, actual outcome, or actual revenue**. Bulk public data can suggest a market; it cannot prove that a Nepali customer will buy. The system should prefer a small number of honest local experiments over large counts of scraped content.

Minors require additional safeguards. ForgeOS may help a 14–17-year-old learn, plan, create a portfolio, and pursue age-appropriate work, but it must not encourage unsafe work, evasion of school or labor rules, deceptive identity use, or unapproved financial activity. Paid work, contracts, account ownership, identity verification, customer contact, and payment-provider onboarding must follow Nepalese law and the provider's current KYC/merchant rules. Where required, involve a parent or guardian and an adult-owned merchant/payment account. ForgeOS should never request or store unnecessary citizenship, wallet PINs, OTPs, or payment credentials.

## First earning pathways

The first release should support several low-capital pathways rather than forcing every user into one business model.

| Pathway | Example first offer | Reality test | Payment route |
|---|---|---|---|
| Local service | tutoring, translation, design, bookkeeping, social-media help, phone repair coordination | one named local customer confirms the need and price | eSewa/Khalti collection; Fonepay/QR for in-person commerce |
| Digital micro-service | poster design, short-video editing, data entry, Nepali-English transcription | customer accepts a sample and pays for one small deliverable | verified eSewa/Khalti checkout |
| Local commerce | pre-order snacks, crafts, repair parts, farm products | paid or deposit-backed pre-order from a real customer | QR/payment provider plus offline order queue |
| Distribution/agent | connect an existing local producer to shops or buyers | producer and buyer both confirm terms; commission is recorded | provider collection or documented bank settlement |
| Skill-to-work pathway | portfolio, apprenticeship, or project-based work | real employer/client response, not a generated job claim | payment only after actual engagement |

ForgeOS should begin with one focused cohort—such as independent repair shops and local digital/service workers—then expand when an actual outcome supports expansion.

## Nepal payment integration priorities

### eSewa

Use the official ePay or Intent flow after merchant approval. Persist the transaction UUID or booking/correlation ID locally, verify signed callbacks/responses, compare amount/product/order identifiers, and query status after timeout or ambiguous responses. eSewa's public documentation describes PENDING, COMPLETE, FAILED, CANCELED, REVERTED, refund, and service-unavailable states. Production credentials, merchant eligibility, settlement timing, fees, limits, and any payout/distribution capability must be confirmed directly with eSewa.

### Khalti by IME

Use the current Khalti KPG-2 flow rather than assuming a standalone IME Pay integration. Initiate server-side, persist the pidx and purchase-order ID, treat the browser return URL as a notification only, and perform server-side lookup. Only **Completed** may trigger fulfillment. Pending, initiated, expired, canceled, failed, refunded, and partially refunded states remain unresolved or reversed until reconciled. The separate Khalti Services API is relevant only for approved service/bill-style products and requires DLR/lookup handling.

### Fonepay

Treat Fonepay as a QR/POS and acquiring-bank integration for Nepal local commerce. Its public material supports merchant QR, Dynamic QR, Checkout, Business App, settlement, and some FoneTAG/CPQR behavior, but does not publish enough technical detail to safely claim a general public API, signed webhook, offline authorization, or payout rail. ForgeOS should not implement against unofficial tutorials. Obtain the current integration pack from Fonepay or the acquiring bank before production work.

## Resilience architecture

The local SQLite database remains the operational source of truth. External operations use the durable integration outbox:

1. Save the intent and idempotency key locally.
2. Attempt delivery only when a provider adapter is configured.
3. Record provider response, status, attempts, and last error.
4. Retry bounded transient failures with backoff.
5. Reconcile pending/ambiguous transactions through provider lookup.
6. Require provider-confirmed success before fulfillment or revenue recognition.
7. Leave an operator task when the provider is unavailable or the state is contradictory.

No provider is treated as the only way to run ForgeOS. If the internet, provider, model, or hosting service is unavailable, users can still work locally and synchronize later without fabricating success.

## Product economics

ForgeOS should earn only through transparent value delivered to users or businesses. Initial options to test are:

- a small paid workflow or setup fee for a business;
- a subscription for verified operational tools after demonstrated value;
- a clearly disclosed service fee for optional payment/reconciliation support, only where legally and contractually permitted;
- partner or distributor commissions recorded as actual revenue only after settlement evidence;
- institution/cohort licensing for schools, cooperatives, local business groups, or training programs.

Do not monetize by promising income, charging vulnerable users for speculative opportunities, selling personal data, taking hidden payment surcharges, or presenting scraped opportunities as guaranteed work.

## Milestones

1. **Truthful local pilot:** one Nepalese cohort, one pathway, zero fabricated activity.
2. **Human validation:** at least five named real users confirm the same problem and workflow value.
3. **Paid pilot:** one real customer pays through a verified channel.
4. **Outcome learning:** compare the predicted result with the actual result and store a lesson.
5. **Repeatability:** three or more independent paying customers or business clients with documented delivery cost, support burden, and retention.
6. **Expansion:** only then add additional pathways, languages, integrations, and cohorts.

The success metric is not “every Nepali profits.” The defensible metric is: **how many real people completed a safe, transparent, profitable-enough earning experiment with evidence of customer demand and no hidden harm?**

## Sources reviewed

- [eSewa Developer Documentation](https://developer.esewa.com.np/), [ePay](https://developer.esewa.com.np/pages/Epay), [Intent](https://developer.esewa.com.np/pages/Intent), and [merchant requirements](https://blog.esewa.com.np/documents-required-esewa-merchant-api-integration)
- [Khalti Developer Documentation](https://docs.khalti.com/), [KPG-2](https://docs.khalti.com/khalti-epayment/), [transaction status](https://docs.khalti.com/api/transaction_status/), and [merchant terms](https://khalti.com/info/terms/merchant/)
- [Fonepay Business](https://fonepay.com/business), [Dynamic QR](https://fonepay.com/blogs/fonepay-dynamic-qr-code), [Checkout](https://fonepay.com/customers/checkout-by-fonepay), and [Merchant Onboarding Best Practices](https://fonepay.com/files/publications/1752402123_MerchantOnboardingBestPractices.pdf)
- [Nepal Rastra Bank NepalQR framework](https://www.nrb.org.np/psd/nepalqr-standardization-framework-and-guidelines/)
- [Nepal Rastra Bank licensed payment-system list](https://www.nrb.org.np/psd/licensed-list-of-payment-system-operator-pso-and-payment-service-provider-psp/)
- [U.S. Department of Commerce Nepal distribution channels](https://www.trade.gov/country-commercial-guides/nepal-distribution-sales-channels)
