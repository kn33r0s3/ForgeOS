/** User-facing identity providers supported by Hami. */
export const AUTH_PROVIDERS = [
  { providerId: "google", label: "Google" },
] as const;

export type AuthProviderId = (typeof AUTH_PROVIDERS)[number]["providerId"];
