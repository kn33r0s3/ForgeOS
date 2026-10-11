export function env(key: string): string | undefined {
  const v = process.env[key]?.trim();
  return v || undefined;
}

/**
 * Grok workspace preview vs a deployed app.
 *
 * GROK_PROJECT_ID identifies a configured Grok deployment, but its absence is
 * not proof that code is running inside that platform's editor. Vercel and
 * production runtimes are deployed environments even when Grok-specific
 * variables are not present.
 */
/** Accept only a network-addressable PostgreSQL URL for durable production auth. */
export function isDurablePostgresDatabaseUrl(value: string | undefined): boolean {
  if (!value) return false;
  try {
    const parsed = new URL(value);
    return (
      (parsed.protocol === "postgres:" || parsed.protocol === "postgresql:") &&
      parsed.hostname.length > 0 &&
      parsed.pathname.length > 1
    );
  } catch {
    return false;
  }
}

export function isWorkspacePreview(): boolean {
  if (env("GROK_PROJECT_ID")) return false;
  if (env("VERCEL") || env("VERCEL_ENV")) return false;
  if (env("NODE_ENV") === "production") return false;
  return true;
}
