/**
 * Set this only after an approved Hami terms document is published. Until
 * then, account creation is deliberately unavailable.
 */
export const ACTIVE_TERMS: { version: string; url: string } | null = null;
