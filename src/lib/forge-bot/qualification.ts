export type QualificationAnswers = {
  destination: string;
  course: string;
  timeline: string;
  budgetMinimum: string;
  budgetMaximum: string;
};

export type DemoContact = {
  email: string;
  phone: string;
};

export type QualificationStage =
  | "INQUIRY"
  | "QUALIFYING"
  | "READY_FOR_OWNER_REVIEW";

export const EMPTY_QUALIFICATION_ANSWERS: QualificationAnswers = {
  destination: "",
  course: "",
  timeline: "",
  budgetMinimum: "",
  budgetMaximum: "",
};

export function qualificationStage(
  answers: QualificationAnswers,
): QualificationStage {
  const values = [
    answers.destination,
    answers.course,
    answers.timeline,
    answers.budgetMinimum,
    answers.budgetMaximum,
  ];
  if (values.every((value) => value.trim() === "")) return "INQUIRY";

  const minimum = Number(answers.budgetMinimum);
  const maximum = Number(answers.budgetMaximum);
  const complete =
    values.every((value) => value.trim() !== "") &&
    Number.isFinite(minimum) &&
    Number.isFinite(maximum) &&
    minimum >= 0 &&
    maximum >= minimum;

  return complete ? "READY_FOR_OWNER_REVIEW" : "QUALIFYING";
}

export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

export function normalizePhone(value: string): string {
  return value.replace(/\D/g, "");
}

export function validateTestContact(contact: DemoContact): string | null {
  const email = normalizeEmail(contact.email);
  const phone = normalizePhone(contact.phone);
  if (!email && !phone) return "Enter a reserved TEST email or phone number.";

  if (email && !/^[^@\s]+@example\.test$/.test(email)) {
    return "Use an email at the reserved example.test domain.";
  }
  if (phone && !/^(?:120255501\d{2}|20255501\d{2})$/.test(phone)) {
    return "Use the reserved 202-555-0100–0199 TEST number range.";
  }
  return null;
}

export function hasDuplicateTestContact(
  saved: readonly DemoContact[],
  candidate: DemoContact,
): boolean {
  const email = normalizeEmail(candidate.email);
  const phone = normalizePhone(candidate.phone);
  return saved.some(
    (existing) =>
      (email && normalizeEmail(existing.email) === email) ||
      (phone && normalizePhone(existing.phone) === phone),
  );
}
