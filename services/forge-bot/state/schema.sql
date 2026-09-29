-- Forge Bot v0 state model (Postgres). Status: TARGET ARCHITECTURE.
-- Used by self-hosted n8n workflows. Minimal personal data by design.

CREATE TABLE IF NOT EXISTS client_config (
  client_id            TEXT PRIMARY KEY,
  business_name        TEXT NOT NULL,
  owner_email          TEXT NOT NULL,
  timezone             TEXT NOT NULL DEFAULT 'Asia/Kathmandu',
  quiet_start          TIME NOT NULL DEFAULT '20:00',
  quiet_end            TIME NOT NULL DEFAULT '08:00',
  followup_days        INTEGER[] NOT NULL DEFAULT '{1,3,7}',
  booking_url          TEXT,
  budget_bands         JSONB NOT NULL DEFAULT '[]',   -- e.g. ["under NPR 15L","15-30L","30L+"]
  approved_faq         JSONB NOT NULL DEFAULT '[]',   -- [{"q":...,"a":...}] client-approved answers only
  stop_keywords        TEXT[] NOT NULL DEFAULT '{STOP,UNSUBSCRIBE}',
  retention_days       INTEGER NOT NULL DEFAULT 180,
  active               BOOLEAN NOT NULL DEFAULT TRUE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
  lead_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id            TEXT NOT NULL REFERENCES client_config(client_id),
  name                 TEXT,
  email                TEXT,
  phone                TEXT,
  source               TEXT NOT NULL,                 -- web_form | email | whatsapp | messenger
  destination          TEXT,
  course               TEXT,
  timeline             TEXT,
  budget_band          TEXT,
  status               TEXT NOT NULL DEFAULT 'new'
                       CHECK (status IN ('new','contacted','qualifying','qualified','booking_sent','booked','escalated','cold','opted_out')),
  consent_contact      BOOLEAN NOT NULL DEFAULT FALSE,
  opted_out_at         TIMESTAMPTZ,                   -- once set, never cleared
  followups_sent       INTEGER NOT NULL DEFAULT 0,
  last_inbound_at      TIMESTAMPTZ,                   -- drives WhatsApp 24h window in v1
  last_outbound_at     TIMESTAMPTZ,
  next_action_at       TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS leads_client_email_uq ON leads (client_id, lower(email)) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS leads_client_phone_uq ON leads (client_id, phone) WHERE phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS leads_due_idx ON leads (next_action_at) WHERE status IN ('contacted','qualifying','qualified','booking_sent');

-- Permanent opt-out registry, independent of lead rows (survives lead archival).
CREATE TABLE IF NOT EXISTS opt_outs (
  client_id            TEXT NOT NULL REFERENCES client_config(client_id),
  contact              TEXT NOT NULL,                 -- lowercased email or E.164 phone
  channel              TEXT NOT NULL,
  opted_out_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  evidence             TEXT,                          -- message id / text that triggered it
  PRIMARY KEY (client_id, contact)
);

CREATE TABLE IF NOT EXISTS messages (
  message_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id              UUID NOT NULL REFERENCES leads(lead_id),
  direction            TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
  channel              TEXT NOT NULL,
  kind                 TEXT NOT NULL,                 -- reply | followup | booking_link | holding | template
  body                 TEXT,                          -- purged after client retention_days
  external_id          TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_lead_idx ON messages (lead_id, created_at);

CREATE TABLE IF NOT EXISTS escalations (
  escalation_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id              UUID NOT NULL REFERENCES leads(lead_id),
  reason               TEXT NOT NULL,                 -- off_faq | visa_admission_job_fee | complaint | legal_refund | minor | low_confidence
  question             TEXT,
  resolved_at          TIMESTAMPTZ,
  resolved_by          TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Owner interventions, for the owner-dependency metric (AGENTS.md top rule).
CREATE TABLE IF NOT EXISTS owner_interventions (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id            TEXT NOT NULL REFERENCES client_config(client_id),
  lead_id              UUID REFERENCES leads(lead_id),
  kind                 TEXT NOT NULL,                 -- approval | escalation_handled | manual_booking | config_change | error
  minutes              INTEGER,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
