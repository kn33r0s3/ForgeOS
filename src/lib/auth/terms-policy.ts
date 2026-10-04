/**
 * Published Hami Terms of Service. When this is set, account creation
 * becomes available through the signup gate (18+ age check + terms acceptance).
 */
export const ACTIVE_TERMS: { version: string; url: string } | null = {
  version: "1.0",
  url: "/terms",
};
