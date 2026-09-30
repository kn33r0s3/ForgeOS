import { EXECUTION_BUDGET_MS, MAX_INPUT_BYTES, TriageError, triage } from "./triage.ts";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

/** Framework-neutral handler. It deliberately never fetches, executes, or persists user input. */
export async function handleEvidenceTriage(request: Request): Promise<Response> {
  if (request.method !== "POST") return json({ error: { code: "METHOD_NOT_ALLOWED" } }, 405);
  if (!request.headers.get("content-type")?.toLowerCase().includes("application/json")) return json({ error: { code: "UNSUPPORTED_MEDIA_TYPE" } }, 415);
  const length = Number(request.headers.get("content-length") ?? "0");
  if (!Number.isFinite(length) || length > MAX_INPUT_BYTES) return json({ error: { code: "PAYLOAD_TOO_LARGE" } }, 413);
  let raw: string;
  try { raw = await request.text(); } catch { return json({ error: { code: "INVALID_BODY" } }, 400); }
  if (new TextEncoder().encode(raw).byteLength > MAX_INPUT_BYTES) return json({ error: { code: "PAYLOAD_TOO_LARGE" } }, 413);
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch { return json({ error: { code: "INVALID_JSON" } }, 400); }
  const timeout = new Promise<never>((_, reject) => setTimeout(() => reject(new TriageError("TIMEOUT", "Execution budget exceeded.")), EXECUTION_BUDGET_MS));
  try { return json(await Promise.race([triage(parsed), timeout])); }
  catch (error) { const code = error instanceof TriageError ? error.code : "INTERNAL_ERROR"; return json({ error: { code } }, code === "TIMEOUT" ? 503 : 400); }
}
