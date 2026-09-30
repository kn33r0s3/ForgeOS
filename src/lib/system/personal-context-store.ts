import {
  parseState,
  type Known,
  type SystemState,
} from "./state.ts";

export type SqlExecutor = {
  query<T extends Record<string, unknown>>(
    text: string,
    params?: unknown[],
  ): Promise<T[]>;
};

export function normalizePersonalContext(input: unknown): SystemState {
  let raw: string;
  try {
    raw = JSON.stringify(input);
  } catch {
    throw new TypeError("Personal context must be valid JSON data.");
  }
  const parsed = parseState(raw);
  if (!parsed) throw new TypeError("Personal context must use the supported context format.");

  const restate = <T>(known: Known<T>): Known<T> => ({
    ...known,
    provenance: "stated",
  });

  return {
    version: 1,
    location: parsed.location ? restate(parsed.location) : undefined,
    time: parsed.time ? restate(parsed.time) : undefined,
    goals: parsed.goals.map(restate),
    capabilities: parsed.capabilities.map(restate),
    resources: parsed.resources.map(restate),
    constraints: parsed.constraints.map(restate),
    createdAt: parsed.createdAt,
    updatedAt: parsed.updatedAt,
  };
}

export async function loadUserPersonalContext(
  sql: SqlExecutor,
  verifiedUserId: string,
): Promise<SystemState | null> {
  const rows = await sql.query<{ context: unknown }>(
    "select context from user_personal_context where user_id = $1 limit 1",
    [verifiedUserId],
  );
  return rows[0] ? normalizePersonalContext(rows[0].context) : null;
}

export async function saveUserPersonalContext(
  sql: SqlExecutor,
  verifiedUserId: string,
  input: unknown,
): Promise<SystemState> {
  const context = normalizePersonalContext(input);
  await sql.query(
    "insert into user_personal_context (user_id, context) values ($1, $2::jsonb) on conflict (user_id) do update set context = excluded.context, updated_at = now()",
    [verifiedUserId, JSON.stringify(context)],
  );
  return context;
}

export async function deleteUserPersonalContext(
  sql: SqlExecutor,
  verifiedUserId: string,
): Promise<void> {
  await sql.query(
    "delete from user_personal_context where user_id = $1",
    [verifiedUserId],
  );
}
