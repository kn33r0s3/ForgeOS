import { randomBytes, randomUUID } from "node:crypto";
import { createServerFn } from "@tanstack/react-start";
import { setCookie } from "@tanstack/react-start/server";
import { z } from "zod";
import { getSql } from "@/lib/db";
import { evaluateSignupRequirements } from "./age-policy";
import { assertSameSiteRequest } from "./isolation.server";
import { ACTIVE_TERMS } from "./terms-policy";

const signupGateInput = z.object({
  dateOfBirth: z.string().optional(),
  acceptedTerms: z.boolean(),
});

export const requestSignupPermit = createServerFn({ method: "POST" })
  .validator((input: unknown) => signupGateInput.parse(input))
  .handler(async ({ data }) => {
    assertSameSiteRequest();
    const now = new Date();
    const eligibility = evaluateSignupRequirements({
      dateOfBirth: data.dateOfBirth,
      acceptedTerms: data.acceptedTerms,
      activeTerms: ACTIVE_TERMS,
      now,
    });
    if (!eligibility.eligible) return eligibility;
    const activeTerms = ACTIVE_TERMS;
    if (!activeTerms) {
      return { eligible: false as const, reason: "terms_not_configured" as const };
    }

    const token = randomBytes(32).toString("base64url");
    const sql = await getSql();
    await sql.query(
      `insert into "verification"
        ("id", "identifier", "value", "expiresAt", "createdAt", "updatedAt")
       values ($1, $2, $3, $4, now(), now())`,
      [
        randomUUID(),
        `hami-signup:${token}`,
        JSON.stringify({
          termsVersion: activeTerms.version,
          termsAcceptedAt: now.toISOString(),
        }),
        new Date(now.getTime() + 5 * 60 * 1000),
      ],
    );
    setCookie("hami_signup_permit", token, {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/api/auth",
      maxAge: 5 * 60,
    });
    return { eligible: true as const };
  });
