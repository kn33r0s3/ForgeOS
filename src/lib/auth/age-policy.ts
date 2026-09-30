export type AgeGateFailure =
  | "dob_required"
  | "dob_invalid"
  | "under_18"
  | "terms_not_configured"
  | "terms_acceptance_required";

export type ActiveTerms = { version: string; url: string } | null;

export type AgeEligibility =
  | { eligible: true }
  | { eligible: false; reason: "dob_required" | "dob_invalid" | "under_18" };

export function evaluateAdultEligibility(
  dateOfBirth: unknown,
  now = new Date(),
): AgeEligibility {
  if (typeof dateOfBirth !== "string" || !dateOfBirth.trim()) {
    return { eligible: false, reason: "dob_required" };
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateOfBirth)) {
    return { eligible: false, reason: "dob_invalid" };
  }

  const [year, month, day] = dateOfBirth.split("-").map(Number);
  const parsed = new Date(0);
  parsed.setUTCHours(0, 0, 0, 0);
  parsed.setUTCFullYear(year, month - 1, day);
  if (
    !Number.isFinite(parsed.getTime()) ||
    parsed.toISOString().slice(0, 10) !== dateOfBirth
  ) {
    return { eligible: false, reason: "dob_invalid" };
  }

  const today = now.toISOString().slice(0, 10);
  if (dateOfBirth > today) return { eligible: false, reason: "dob_invalid" };

  const eighteenthBirthdayYear = year + 18;
  const birthdayInEighteenthYear =
    month === 2 &&
    day === 29 &&
    !isLeapYear(eighteenthBirthdayYear)
      ? `${eighteenthBirthdayYear}-03-01`
      : `${String(eighteenthBirthdayYear).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

  return today >= birthdayInEighteenthYear
    ? { eligible: true }
    : { eligible: false, reason: "under_18" };
}

export function evaluateSignupRequirements(input: {
  dateOfBirth: unknown;
  acceptedTerms: unknown;
  activeTerms: ActiveTerms;
  now?: Date;
}): { eligible: true } | { eligible: false; reason: AgeGateFailure } {
  const age = evaluateAdultEligibility(input.dateOfBirth, input.now);
  if (!age.eligible) return age;
  if (!input.activeTerms) {
    return { eligible: false, reason: "terms_not_configured" };
  }
  if (input.acceptedTerms !== true) {
    return { eligible: false, reason: "terms_acceptance_required" };
  }
  return { eligible: true };
}

export type SignupPermitRecord = { value: string };

export async function consumeSignupPermit(
  cookieHeader: string | null | undefined,
  activeTerms: ActiveTerms,
  consume: (identifier: string) => Promise<SignupPermitRecord | null>,
): Promise<{ termsVersion: string; termsAcceptedAt: Date } | null> {
  if (!activeTerms) return null;
  const token = readCookie(cookieHeader, "hami_signup_permit");
  if (!token || !/^[A-Za-z0-9_-]{40,64}$/.test(token)) return null;

  const row = await consume(`hami-signup:${token}`);
  if (!row) return null;

  try {
    const grant = JSON.parse(row.value) as {
      termsVersion?: unknown;
      termsAcceptedAt?: unknown;
    };
    if (
      grant.termsVersion !== activeTerms.version ||
      typeof grant.termsAcceptedAt !== "string"
    ) {
      return null;
    }
    const termsAcceptedAt = new Date(grant.termsAcceptedAt);
    if (!Number.isFinite(termsAcceptedAt.getTime())) return null;
    return { termsVersion: activeTerms.version, termsAcceptedAt };
  } catch {
    return null;
  }
}

function readCookie(header: string | null | undefined, name: string): string | null {
  for (const part of header?.split(";") ?? []) {
    const trimmed = part.trim();
    const equals = trimmed.indexOf("=");
    if (equals > 0 && trimmed.slice(0, equals) === name) {
      return trimmed.slice(equals + 1);
    }
  }
  return null;
}

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}
