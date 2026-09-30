/**
 * Local preview hosts accepted by Better Auth's request-derived base URL.
 * Direct Google OAuth still needs an exact callback registered with Google;
 * dynamic preview hosts cannot be used as a substitute for that configuration.
 */
export const PREVIEW_ALLOWED_HOSTS = ["*.grok-sandbox.com"] as const;
