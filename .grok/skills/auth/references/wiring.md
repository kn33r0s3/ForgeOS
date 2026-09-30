# Wiring Better Auth routes

The Vite preview popup is pre-wired and must not be replaced by a React route.
It starts direct Google OAuth only when the server has Google credentials.
Never add `src/routes/auth/popup.tsx`.

Mount the app-owned Better Auth API at `/api/auth/*`:

```ts
// src/routes/api/auth/$.ts
import { createFileRoute } from "@tanstack/react-router";
import { auth } from "@/lib/auth/server";

export const Route = createFileRoute("/api/auth/$")({
  server: {
    handlers: {
      GET: ({ request }) => auth.handler(request),
      POST: ({ request }) => auth.handler(request),
    },
  },
});
```

The login page must derive Google availability from a server response and never
send credentials to the client. The server enables `socialProviders.google`
only when both `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are configured.
The OAuth callback is `<HAMI_ORIGIN>/api/auth/callback/google`.

Every user-creation path must pass the server-side 18+ and current-terms gate.
The database hook rejects direct Better Auth signup calls that bypass the page.
Date of birth is not persisted. Until an approved terms document/version is
configured, registration remains closed with a clear placeholder.

Use the existing `<UserButton />` for sign-out. Use `useCurrentUser()` only for
display; guard protected content with verified server functions and
`authMiddleware`. The popup, bearer handoff, and request attachment remain in
the existing auth code.
