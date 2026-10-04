// Angles already tried by the operator's discovery rounds.
// Generated from ~/workspace/discovery/discovery-log.md — regenerate when rounds are added.
// The assistant uses this so it never suggests a repeated angle.

export interface TriedAngle { round: number; angle: string; }

export const triedAngles: TriedAngle[] = [
  { round: 1, angle: "broad forum listening (English, Western-skewed)" },
  { round: 2, angle: "Nepal-first: observe behavior, not just talk" },
  { round: 2, angle: "Nepali TikTok business content + public Facebook commerce" },
  { round: 3, angle: "the counter's question: \"did I actually get paid?\"" },
  { round: 4, angle: "the supply side: kirana economics, udharo, and who finances the stock" },
  { round: 5, angle: "one trade: the mobile repair bench" },
  { round: 6, angle: "one merchant tool: did \"मेरो कारोबार\" survive?" },
  { round: 7, angle: "one failed startup postmortem: what killed Tootle" },
  { round: 8, angle: "one festival: Dashain as the merchant's annual cash-flow event" },
  { round: 9, angle: "one finance rail: the savings-and-credit cooperative (सहकारी)" },
  { round: 10, angle: "one dead marketplace: Sastodeal (the other postmortem)" },
  { round: 11, angle: "one trade: the sunchaandi (gold/jewelry) counter" },
  { round: 12, angle: "one shutter: the landlord economy behind the counter" },
  { round: 13, angle: "one rail: the COD courier (cash carried by hand)" },
];

export const triedAnglesCount = triedAngles.length;
