// Candidate needs found by Hami's discovery rounds.
//
// Every entry is OBSERVED-at-best: seen in public sources (reviews, forums,
// press, app telemetry), paraphrased, never invented. None is verified with
// the people themselves — each is a candidate until a real conversation
// confirms or kills it.
//
// knownToThem marks whether the people feel the need themselves:
//   "known"     — they name it; it hurts out loud.
//   "unknown"   — they don't name it; it shows up in behavior. These are the
//                 higher-value finds: needs people can't ask to have solved.
//   "partially" — half-seen: felt in one segment, invisible in another.

export type KnownToThem = "known" | "unknown" | "partially";

export interface CandidateNeed {
  id: string;
  title: string;
  segment: string;
  knownToThem: KnownToThem;
  need: string;
  observed: string;
  sources: string[];
  round: string;
  question: string;
}

export const KNOWN_LABEL: Record<KnownToThem, string> = {
  known: "Known need — they feel it",
  unknown: "Unknown need — they don't name it",
  partially: "Half-seen — felt in one segment, invisible in another",
};

export const candidateNeeds: CandidateNeed[] = [
  {
    id: "need-missed-inquiry",
    title: "Never miss the inquiry",
    segment: "Social sellers",
    knownToThem: "known",
    need: "Every inquiry answered, fast — a missed message is a missed sale.",
    observed:
      "Commerce runs on conversation: HamroBazaar's call-to-action is 'Call now', sellers put raw phone numbers in listings to defeat masking, and TikTok order flow is DM plus photos plus cash-on-delivery. The phone number is the persistent identifier. A Kathmandu bookstore doing NPR 50k+ a day through TikTok and WhatsApp says it 'can't keep up with orders, replies, videos'.",
    sources: ["HamroBazaar listings", "TikTok seller flows", "Nepali business press"],
    round: "Round 2",
    question:
      "When a customer messages at 9pm, how long until they hear back — and how many never wait?",
  },
  {
    id: "need-response-capacity",
    title: "Capacity to respond, not more customers",
    segment: "One-body merchants",
    knownToThem: "unknown",
    need: "The ability to absorb demand — replies, fulfillment, presence — before chasing more of it.",
    observed:
      "Ask owners what they want and they say customers. Watch what breaks and it's their time: 'If I brought you 10 new customers tomorrow, what breaks?' One mart owner: 'no shortage of customers if I have goods.' Creating, answering, and fulfilling is one body. 'Find opportunities' is the wrong verb — response capacity is the constraint.",
    sources: ["Owner interviews in Nepali press", "forum listening"],
    round: "Rounds 1–2",
    question: "If I brought you 10 new customers tomorrow, what breaks?",
  },
  {
    id: "need-paid-proof",
    title: "“Did I actually get paid?”",
    segment: "QR-accepting counters",
    knownToThem: "known",
    need: "Trustworthy payment confirmation at the counter, on the merchant's own device.",
    observed:
      "Verification is adversarial, not just delayed: customers show fake 'Success' screens. Kathmandu shopkeepers are warned not to hand over goods on the customer's screen — 'check your own bank message, the master logic.' The receipt itself is contested. 'Did I get paid?' is a trust problem at the counter, not a latency problem.",
    sources: ["Nepali creator warnings", "cyber-fraud coverage", "merchant QR app reviews"],
    round: "Round 3",
    question:
      "When a customer shows you a payment screen, what do you trust — the screen, the bank SMS, or your eyes?",
  },
  {
    id: "need-shared-counter",
    title: "Every staffer can verify a payment",
    segment: "Multi-staff shops",
    knownToThem: "known",
    need: "Shared-counter visibility: anyone standing at the counter can check a payment without sharing passwords.",
    observed:
      "The dominant merchant QR app broke multi-device login in an update (rated 2.73/5 across ~1,900 reviews). Owners: 'multiple people need to check customer payments when SMS doesn't arrive' — and 'you can't give everyone the password.' The tool's security model is personal banking; the counter is shared and multi-person.",
    sources: ["Fonepay FoneBiz Play Store reviews", "eSewa Business docs"],
    round: "Round 3",
    question:
      "When it's busy, who at your shop checks the payment — and what slows them down?",
  },
  {
    id: "need-stock-credit",
    title: "Stock credit without the paperwork wall",
    segment: "Unpapered merchants",
    knownToThem: "known",
    need: "Finance the next stock-up without PAN, registration, or bank history.",
    observed:
      "Formal channel financing stops above the papered line: no PAN means cash for stock. Savings-and-credit cooperatives filled the gap — Rs 5–30k shop loans where share-capital membership substitutes for paperwork; the paperless merchant's actual bank. That rail is now tightening under new central-bank caps while co-ops resist registering.",
    sources: ["Brand channel-financing material", "cooperative credit docs", "NRB draft directive"],
    round: "Rounds 4, 9",
    question: "When the shop needs money for stock — bank, सहकारी, or someone's door?",
  },
  {
    id: "need-udharo",
    title: "Udharo that doesn't break the relationship",
    segment: "Kirana counters",
    knownToThem: "known",
    need: "Give credit, get it back, keep the customer.",
    observed:
      "Shop credit starts easy; collecting changes everything: 'the day you ask for the money back, the relationship changes.' It's a national problem — the Chamber of Commerce drafted a Commercial Credit Recovery Bill with fast-track recovery committees. A Nepali ledger app already serves the tracking half (reminders); the collection-without-damage half is open.",
    sources: ["TikTok shopkeeper voices", "Nepal Chamber of Commerce", "मेरो कारोबार"],
    round: "Round 4",
    question:
      "After rent, stock, and the month's udharo that never came back — what lands in your pocket?",
  },
  {
    id: "need-own-calendar",
    title: "Tools in their calendar, their language",
    segment: "Nepali merchants",
    knownToThem: "partially",
    need: "Software that keeps books the way they keep books — Bikram Sambat, Nepali.",
    observed:
      "A Nepali khata app's founder tried Indian ledger apps for his father's shop; they failed on one detail — English dates versus the Nepali calendar his father kept books by. That app now holds 500k+ installs at ~Rs 2,000/year and clears Rs 10M+ in annual revenue. Localization decided the winner, not features or funding.",
    sources: ["App telemetry", "founder interviews", "Bangladeshi user interview"],
    round: "Round 6",
    question: "What detail in your tools feels foreign — and what did you work around?",
  },
  {
    id: "need-season-risk",
    title: "Survive the season you pre-paid for",
    segment: "Festival-stock retailers",
    knownToThem: "unknown",
    need: "Manage pre-commitment risk when the year's biggest season can fail.",
    observed:
      "Dashain concentrates ~30–35% of annual consumption into two months — merchants pre-stock cash into inventory, some of it stranded behind landslide-hit border crossings. In 2026 the season broke: a Koteshwor retailer down 40–45% year-on-year, 'never seen such low business during Dashain except COVID and the 2015 earthquake.' Who eats unsold stock — retailer or distributor — is unmapped.",
    sources: ["Nepali business press", "trader federation quotes", "NRB cash-circulation data"],
    round: "Round 8",
    question:
      "What did you buy in advance for the season — and if the customers don't come, who eats that stock?",
  },
  {
    id: "need-cashflow",
    title: "Cash-flow survival on thin margins",
    segment: "Kirana and repair trades",
    knownToThem: "unknown",
    need: "Survive the float squeeze: sales up, cash gone into stock.",
    observed:
      "A kirana nets around 5% — roughly NPR 20–40k a month — and demand growth eats the cash float immediately. Mobile repair nets ~20% yet 80% of shops close within two years 'due to losses and cash-flow problems.' Owners blame sales; the killer is cash flow.",
    sources: ["Kathmandu Valley kirana study", "repair-training institute data"],
    round: "Rounds 4–5",
    question: "When sales go up, does your cash go up too — or does it disappear into stock?",
  },
  {
    id: "need-money-home",
    title: "A money-home they can trust again",
    segment: "Co-op members, small savers",
    knownToThem: "known",
    need: "A safe place for savings after the trust layer was looted.",
    observed:
      "A 2024 parliamentary probe found ~Rs 87.89 billion misappropriated across 40+ savings cooperatives, with fake audits; ~76,000 depositors are owed ~Rs 46 billion. The state is refunding small depositors; victims are still protesting. The constitution calls cooperatives a pillar of the economy — the pillar went unsupervised for seven decades.",
    sources: ["Parliamentary probe coverage", "Nepali business press", "NRB"],
    round: "Round 9",
    question: "After the scandals, where do you keep the savings now?",
  },
  {
    id: "need-shutter-cycle",
    title: "Break the shutter-rent cycle",
    segment: "Retail shutter tenants",
    knownToThem: "partially",
    need: "Escape the loop: borrow to stock, miss rent, close, landlord re-lets higher.",
    observed:
      "The press names it plainly: merchants borrow to stock the shop, miss two to three months' rent, debt compounds, they close — the shutter re-lets at a higher rent to the next merchant. 'Shutters rotate, merchants rotate, the problem stays.' The press says rent is the #1 complaint; owner behavior says presence binds. The binding constraint is segment-dependent.",
    sources: ["Nepali press", "shop-for-sale listings"],
    round: "Rounds 2, 5",
    question: "What would have to be true for this shutter to still be yours in three years?",
  },
  {
    id: "need-teach-me",
    title: "Teach me, don't sell me",
    segment: "Small owners",
    knownToThem: "known",
    need: "Learn the skill instead of buying the service.",
    observed:
      "A 'be your own marketer' program tours four cities teaching owners to shoot their own videos — 900+ trained. Skill-transfer passes the distrust filter; done-for-you marketing dies. Owners have been burned by scale-assuming spend before, so they trust teaching over selling.",
    sources: ["Nepali creator programs", "forum listening"],
    round: "Rounds 1–2",
    question: "The last time someone tried to sell you growth — what made you say no?",
  },
];

export const needsCount = candidateNeeds.length;
export const needsRounds = 9;
