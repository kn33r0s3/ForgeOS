// Public unknowns projection: every item comes from GET /forge/unknowns
// with its truth label (epistemic_state) and source (provenance).
// Nothing on the page is hand-written.

export interface ApiUnknown {
  id: number;
  row_id: string;
  question: string;
  epistemic_state: string;
  cheapest_test: string;
  provenance: string | null;
}

function apiBase(): string {
  return import.meta.env?.VITE_FORGE_API_BASE?.replace(/\/$/, "") ?? "";
}

export async function fetchUnknowns(): Promise<ApiUnknown[]> {
  const base = apiBase();
  const candidates = [`/api/forge/unknowns`, ...(base ? [`${base}/forge/unknowns`] : [])];
  let lastError: unknown = null;
  for (const url of [...new Set(candidates)]) {
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) {
        lastError = new Error(`HTTP ${res.status}`);
        continue;
      }
      const data = (await res.json()) as ApiUnknown[];
      if (Array.isArray(data)) return data;
      lastError = new Error("unexpected response shape");
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("unknowns unavailable");
}
