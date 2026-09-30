alter table "user"
  add column if not exists "termsVersion" text,
  add column if not exists "termsAcceptedAt" timestamptz;
