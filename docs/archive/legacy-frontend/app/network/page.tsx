"use client";

import { useEffect, useState } from "react";
import { api, NetworkConnectionRow } from "@/lib/api";

export default function NetworkPage() {
  const [rows, setRows] = useState<NetworkConnectionRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api.listNetworkConnections()
      .then((loaded) => {
        if (active) setRows(loaded);
      })
      .catch(() => {
        if (active) setError("The connection list could not be loaded.");
      });
    return () => {
      active = false;
    };
  }, []);

  async function scan() {
    setBusy(true); setError(null);
    try { await api.scanNetworkConnections(); const loaded = await api.listNetworkConnections(); setRows(loaded); }
    catch (err) { setError(err instanceof Error ? err.message : "The backend refused the scan."); }
    finally { setBusy(false); }
  }

  async function advance(id: number, nextState: string) {
    setBusy(true); setError(null);
    try { await api.advanceNetworkConnection(id, nextState); setRows(await api.listNetworkConnections()); }
    catch (err) { setError(err instanceof Error ? err.message : "The backend refused the state change."); }
    finally { setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <p className="text-xs uppercase tracking-[0.14em] text-forge-accent2">Network</p>
      <h1 className="mt-2 text-3xl text-white">Candidate connections</h1>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-neutral-400">
        These are internal possibilities. A candidate is not an offer. A proposal exists only when stored external evidence was cited. The public site shows a connection only after it is authorized and published.
      </p>
      <button type="button" disabled={busy} onClick={() => void scan()} className="mt-6 rounded-full bg-white px-4 py-2 text-sm text-black disabled:opacity-50">{busy ? "Working…" : "Scan existing candidates"}</button>
      {error ? <p className="mt-6 text-sm text-neutral-300">{error}</p> : null}
      {!error && rows.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-400">No connections are stored.</p>
      ) : null}
      <div className="mt-6 space-y-3">
        {rows.map((row) => (
          <article key={row.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-neutral-300">
            <p className="text-white">{row.left_kind} {row.left_id} → {row.right_kind} {row.right_id}</p>
            <p className="mt-1">State: {row.state} · {row.public_visible ? "public" : "internal"}</p>
            <p className="mt-1">{row.reason}</p>
            <p className="mt-1">{row.evidence_reference || "No evidence reference"}</p>
            <p className="mt-1">{row.constraints || "No viability quotes recorded. Cost, margin, buyer, and route stay unknown."}</p>
            <p className="mt-1">{row.seconds_to_recorded_payment == null ? "No recorded payment yet." : `Recorded payment ${row.seconds_to_recorded_payment}s after the connection.`}</p>
            <p className="mt-1">{row.latest_response || "No response recorded. A response is not acceptance."}</p>
            <p className="mt-1">{row.unknown || "Unknowns not recorded"}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {row.state === "candidate" ? <button type="button" disabled={busy} onClick={() => void advance(row.id, "proposed")} className="rounded-full border border-white/20 px-3 py-1.5 text-xs text-white disabled:opacity-50">Propose</button> : null}
              {row.state === "proposed" ? <button type="button" disabled={busy} onClick={() => void advance(row.id, "authorized")} className="rounded-full border border-white/20 px-3 py-1.5 text-xs text-white disabled:opacity-50">Authorize</button> : null}
              {row.state === "authorized" ? <button type="button" disabled={busy} onClick={() => void advance(row.id, "contacted")} className="rounded-full border border-white/20 px-3 py-1.5 text-xs text-white disabled:opacity-50">Mark contacted</button> : null}
              {row.public_visible ? <span className="rounded-full border border-forge-revenue/30 px-3 py-1.5 text-xs text-forge-revenue">Published</span> : null}
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
