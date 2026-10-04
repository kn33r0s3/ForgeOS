/**
 * Email/password sign-in using this app's Better Auth database.
 *
 * Enabled for the private personal-context account flow. The account owns
 * only private context; authentication does not authorize public sharing.
 *
 * NOTE: the "frozen pre-wired config" claim that used to live here is stale —
 * `server.ts` has since been customized (age/terms signup gate, gate-identity
 * plugin, Hami terms copy). Edit `server.ts` deliberately, with the auth
 * boundary tests (`auth-boundary.test.ts`) as the guardrails.
 */
export const emailAndPasswordEnabled = true;
