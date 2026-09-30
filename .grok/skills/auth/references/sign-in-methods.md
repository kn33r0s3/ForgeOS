# Supported sign-in methods

Hami's user-facing methods are:

- **Google**, using Better Auth's direct Google integration. It is enabled only
  when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are present server-side.
- **Email + password**, using this app's own Better Auth database.

Do not expose X/Twitter or route Google through `auth.grok.me` or another
identity broker. Do not add unrelated OAuth methods, magic links, passkeys,
one-time codes, phone/SMS, or anonymous sign-in.

## Account creation

Every new user, regardless of provider, must be at least 18 and explicitly
accept the currently configured Hami terms. The server validates the supplied
date of birth against the UTC civil date and consumes a short-lived, single-use
permit in Better Auth's existing verification table before creating the user.
The date of birth is not stored. A successful account row retains only the
accepted terms version and timestamp.

No Hami terms document is currently configured. `ACTIVE_TERMS` therefore
remains `null`, the UI explains that registration is unavailable, and the
server refuses to issue a permit or create a new account. Do not invent legal
terms or change this gate until an approved document and version are supplied.

The age boundary is the 18th birthday in the UTC civil-date convention. The
birthday itself is eligible. For a February 29 birth in a non-leap year, the
18th birthday is treated as March 1. A malformed or future date is rejected.
This is self-reported eligibility, not identity or age verification.

## Direct Google configuration

Use the installed Better Auth `socialProviders.google` integration. Configure
the exact callback URI `<HAMI_ORIGIN>/api/auth/callback/google` in the Google
OAuth client, and inject `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` on the
server. Never expose the secret to Vite or the browser. If credentials or a
registered callback are missing, show Google as unavailable rather than
silently routing elsewhere.

## Existing protections

- Same-origin Better Auth sessions use the app's existing `__Host-` cookies and
  `trustedOrigins`; do not weaken them to suppress an origin error.
- `authMiddleware` verifies the session and rejects cross-site server-function
  requests before private data access.
- Every private context query remains scoped to verified `context.userId`.
- New accounts persist only required consent metadata. DOB, eligibility input,
  and private context do not enter public feeds, networks, or discovery
  projections.
