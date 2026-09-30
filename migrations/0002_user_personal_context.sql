create table if not exists user_personal_context (
  user_id text primary key references "user" ("id") on delete cascade,
  context jsonb not null check (jsonb_typeof(context) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
