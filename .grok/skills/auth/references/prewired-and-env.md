# What's pre-wired, and the environment variables

## `src/lib/auth/`

| File | Use it for |
|---|---|
| `client.ts` | Browser Better Auth client, direct sign-in popup, bearer handoff, and sign-out. |
| `server.ts` | Server-only Better Auth instance, direct Google provider, and account-create hook. |
| `email-password.ts` | Existing local email/password switch. |
| `providers.ts` | Client-safe Hami provider allowlist; currently Google only. |
| `availability.ts` | Server-derived provider and terms availability; never returns secrets. |
| `signup-gate.server.ts` | Issues a short-lived one-time permit after DOB and terms checks. |
| `age-policy.ts` | UTC civil-date age rule and permit consumption. DOB is not stored. |
| `terms-policy.ts` | Approved terms version and URL. `null` keeps registration closed. |
| `popup.server.ts` | Direct provider popup used by the local preview plugin. |
| `middleware.ts` | `authMiddleware` for server functions → verified `context.userId`. |
| `verify.server.ts` | `requireUserId()` / `getSessionUser()` for server-side session checks. |

## Credentials and provider behavior

- **Google** is Better Auth's built-in `socialProviders.google` provider. It
  uses Google's own OAuth endpoints and the callback
  `<HAMI_ORIGIN>/api/auth/callback/google`. The runtime needs both
  `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. They are server-only; if either
  is missing, the UI disables Google and explains why. Never replace this with
  a broker or a demo redirect.
- Dynamic preview hostnames are not automatically valid Google OAuth callback
  URLs. Register each exact callback with Google or use a stable Hami origin.
- Google sign-up is explicit (`requestSignUp`) and remains subject to the same
  server-side age/terms gate as email signup.
- **Email/password** uses this app's Better Auth database, with the existing
  PGLite local fallback and Postgres deployment adapter. New-user creation is
  denied by the database hook unless a one-time age/terms permit is consumed.
- DOB is validated in memory only and is never stored in the user row, URL,
  public projection, or log. A successful signup records only the accepted
  terms version and timestamp.

## Environment variables

Do not store credentials in `.grok/app-env.json`, any `VITE_` variable, or a
tracked file. Supply provider credentials through the local process environment
or the deployment's server-only environment configuration.

| Variable | Purpose |
|---|---|
| `GOOGLE_CLIENT_ID` | Direct Google OAuth client id, server-side. |
| `GOOGLE_CLIENT_SECRET` | Direct Google OAuth client secret, server-side only. |
| `BETTER_AUTH_URL` | Stable public Hami origin when one is configured. |
| `BETTER_AUTH_SECRET` | Signs this app's Better Auth sessions. |
| `DATABASE_URL` | Optional Postgres connection; local development uses PGLite without it. |
| `VITE_AUTH_ENABLED` | Public feature flag only; never put credentials in it. |

There is no baked preview OAuth client or fallback issuer. `src/lib/auth/terms-policy.ts`
must point to an approved, current legal document before signup is enabled;
until then its `ACTIVE_TERMS` value intentionally stays `null`.
