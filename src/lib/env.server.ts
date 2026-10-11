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
export function isWorkspacePreview(): boolean {
  if (env("GROK_PROJECT_ID")) return false;
  if (env("VERCEL") || env("VERCEL_ENV")) return false;
  if (env("NODE_ENV") === "production") return false;
  return true;
}
