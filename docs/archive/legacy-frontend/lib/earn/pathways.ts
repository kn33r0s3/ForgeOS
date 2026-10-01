export type EarningPathway = {
  id: string;
  title: string;
  nepali: string;
  examples: string;
  firstTest: string;
  nextActions: string[];
};

export const pathways: EarningPathway[] = [
  {
    id: "local-service",
    title: "Local service",
    nepali: "स्थानीय सेवा",
    examples: "Tutoring, repair coordination, translation, bookkeeping, social media help",
    firstTest: "Find one named local customer and confirm the need and price.",
    nextActions: [
      "Write a one-sentence offer with price in NPR",
      "Message or visit 1–3 real people who might need it",
      "Ask if they would pay that price for a first small job",
      "If yes, deliver a tiny version and request payment",
    ],
  },
  {
    id: "digital",
    title: "Digital micro-service",
    nepali: "डिजिटल सानो सेवा",
    examples: "Poster design, short-video editing, data entry, Nepali–English transcription",
    firstTest: "Send one sample and ask one real customer for a paid trial.",
    nextActions: [
      "Make one small sample (even rough is fine)",
      "Send it to one real person/business",
      "Ask for a paid mini-job at a clear NPR price",
      "Deliver and collect payment only after agreement",
    ],
  },
  {
    id: "commerce",
    title: "Local commerce",
    nepali: "स्थानीय व्यापार",
    examples: "Snacks, crafts, farm products, repair parts, pre-orders",
    firstTest: "Collect a real pre-order or deposit before buying stock.",
    nextActions: [
      "List the exact item and your NPR price",
      "Ask 3 people if they would pre-order",
      "Only buy stock after at least one real commitment",
      "Record payment only when money is received",
    ],
  },
  {
    id: "agent",
    title: "Agent / distribution",
    nepali: "एजेन्ट / वितरण",
    examples: "Connect producers, shops, buyers, and service providers",
    firstTest: "Get both sides to confirm terms and record the commission.",
    nextActions: [
      "Name one producer and one possible buyer",
      "Confirm both sides are interested in principle",
      "Agree a clear commission or fee in NPR",
      "Record outcome only after a real transaction",
    ],
  },
  {
    id: "skill-work",
    title: "Skill-to-work",
    nepali: "सीपबाट काम",
    examples: "Portfolio, apprenticeship, project-based work",
    firstTest: "Get a real client or employer response—not a generated promise.",
    nextActions: [
      "Prepare a short proof of skill (photo, sample, link)",
      "Contact one real client or local business",
      "Ask for a small paid trial or clear no",
      "Log the real response",
    ],
  },
];
