"use client";

import { useEffect, useState } from "react";
import { api, ActionPackage, ExecutionAction, ForgeApiError, actionStage, computeProfit } from "@/lib/api";
import GlassPanel from "@/components/GlassPanel";
import StatusPill from "@/components/StatusPill";
import { useForgeQuery } from "@/lib/useForgeQuery";
import QueryStateView from "@/components/QueryStateView";

const STAGES = ["DISCOVERED", "VALIDATED", "STRATEGY CREATED", "EXPERIMENT", "EXECUTION", "RESULT", "REVENUE", "LEARNING"];

function stageIndexFor(a: ExecutionAction): number {
  const stage = actionStage(a);
  if (stage === "verified") return 7;
  if (stage === "completed") return 5;
  if (stage === "attempted") return 4;
  if (a.requires_owner_approval && !a.approved_at) return 1;
  return 2;
}

function lifecycleLabel(a: ExecutionAction): string {
  if (a.status === "blocked") return "BLOCKED";
  if (a.requires_owner_approval && !a.approved_at) return "OWNER AUTHORIZATION REQUIRED";
  if (a.requires_owner_approval && a.approved_at && !a.started_at) return "AUTHORIZED";
  if (a.started_at && !a.completed_at) return "EXECUTING";
  if (a.completed_at) return "COMPLETED";
  return a.status;
}

export default function ExecutionPage() {
  const { state, data, error, reload } = useForgeQuery<ExecutionAction[]>(
    () => api.getExecutionActions(),
    (d) => d.length === 0
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">EXECUTION</h1>
        <p className="text-sm text-neutral-500 mt-1">
          The real lifecycle of every action Forge has proposed — nothing here is marked
          complete unless the backend actually recorded a result.
        </p>
      </div>

      {state !== "ready" && (
        <QueryStateView
          state={state}
          error={error}
          emptyLabel="No execution actions exist yet. Create one from an opportunity's detail view."
          onRetry={reload}
        />
      )}

      {state === "ready" && data && (
        <div className="grid gap-4">
          {data.map((action) => (
            <ExecutionCard key={action.id} action={action} onChanged={reload} />
          ))}
        </div>
      )}
    </div>
  );
}

function needsApproval(action: ExecutionAction): boolean {
  return action.policy_decision === "require_approval";
}

function apiMessage(err: unknown): string {
  if (err instanceof ForgeApiError) {
    try {
      const body = JSON.parse(err.message) as { detail?: unknown };
      if (typeof body.detail === "string") return body.detail;
    } catch {
      return err.message;
    }
    return err.message;
  }
  return "Request failed";
}

function ExecutionCard({ action, onChanged }: { action: ExecutionAction; onChanged: () => void }) {
  const approval = needsApproval(action);
  const [busy, setBusy] = useState(false);
  const [showResultForm, setShowResultForm] = useState(false);
  const [showPaymentForm, setShowPaymentForm] = useState(false);
  const [result, setResult] = useState("");
  const [revenue, setRevenue] = useState("");
  const [conversions, setConversions] = useState("");
  const [costs, setCosts] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [paymentSource, setPaymentSource] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [pkg, setPkg] = useState<ActionPackage | null>(null);

  const profit = computeProfit(action);
  const activeIndex = stageIndexFor(action);
  const label = lifecycleLabel(action);

  useEffect(() => {
    if (!approval) return;
    let cancelled = false;
    api.getActionPackage(action.id).then(
      (loaded) => {
        if (!cancelled) setPkg(loaded);
      },
      () => {
        if (!cancelled) setPkg(null);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [approval, action.id, action.result, action.revenue]);

  async function handleApprove() {
    setBusy(true);
    setFormError(null);
    try {
      await api.approveExecutionAction(action.id);
      onChanged();
    } catch (err) {
      setFormError(apiMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleStart() {
    setBusy(true);
    setFormError(null);
    try {
      await api.startExecutionAction(action.id);
      onChanged();
    } catch (err) {
      setFormError(apiMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRecordResult() {
    if (!result.trim()) return;
    setBusy(true);
    setFormError(null);
    try {
      if (approval) {
        await api.recordHumanResult(action.id, result.trim());
      } else {
        await api.recordExecutionResult(action.id, {
          result,
          revenue: revenue ? parseFloat(revenue) : undefined,
          conversions: conversions ? parseInt(conversions, 10) : undefined,
          costs: costs ? parseFloat(costs) : undefined,
        });
      }
      setShowResultForm(false);
      onChanged();
    } catch (err) {
      setFormError(apiMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifiedPayment() {
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed < 0 || currency.trim().length !== 3 || !paymentSource.trim() || !paymentReference.trim()) {
      setFormError("Amount, a 3-letter currency, source, and payment reference are required.");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      await api.recordVerifiedRevenue(action.id, {
        amount: parsed,
        currency: currency.trim().toUpperCase(),
        source: paymentSource.trim(),
        reference: paymentReference.trim(),
      });
      setShowPaymentForm(false);
      onChanged();
    } catch (err) {
      setFormError(apiMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <GlassPanel className="p-5">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-widest text-neutral-500 mb-1">
            {action.action_type || "action"}
          </p>
          <p className="text-sm font-medium text-neutral-100">{action.action}</p>
        </div>
        <StatusPill label={label} />
      </div>

      {/* Lifecycle progression */}
      <div className="flex items-center gap-1 overflow-x-auto py-2">
        {STAGES.map((s, i) => (
          <div key={s} className="flex items-center shrink-0">
            <div
              className={`h-1.5 w-10 rounded-full ${
                i <= activeIndex ? "energy-flow" : "bg-forge-border"
              }`}
              title={s}
            />
          </div>
        ))}
      </div>
      <p className="text-[10px] text-neutral-600 uppercase tracking-wide mb-3">
        {STAGES[Math.min(activeIndex, STAGES.length - 1)]}
      </p>

      {approval && pkg && (pkg.problem || pkg.evidence.length > 0) && (
        <div className="mb-3 space-y-2">
          {pkg.problem && (
            <p className="text-sm text-neutral-300">
              <span className="text-neutral-500">Problem: </span>
              {pkg.problem}
            </p>
          )}
          {pkg.evidence.map((item) => (
            <p key={item.signal_id} className="text-xs text-neutral-400 leading-relaxed border-l border-forge-border pl-3">
              {item.text}
            </p>
          ))}
        </div>
      )}

      {action.result && (
        <div className="text-sm text-neutral-300 mb-3">
          <span className="text-neutral-500">Result: </span>
          {action.result}
        </div>
      )}

      {action.policy_reason && (
        <div className="text-xs text-neutral-500 mb-3 leading-relaxed">
          <span className="uppercase tracking-wide text-neutral-600">Policy: </span>
          {action.policy_reason}
          {action.risk_score !== null && <span className="ml-2 text-neutral-600">risk {action.risk_score.toFixed(0)}/100</span>}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-3">
        <MetricBox label="Revenue" value={action.revenue !== null ? `$${action.revenue.toFixed(2)}` : "unknown"} />
        <MetricBox label="Costs" value={action.costs !== null ? `$${action.costs.toFixed(2)}` : "unknown"} />
        <MetricBox label="Profit" value={profit !== null ? `$${profit.toFixed(2)}` : "unknown"} />
      </div>

      {action.status === "blocked" ? (
        <p className="text-xs text-forge-danger">
          Blocked by policy — this cannot be started or approved. Adjust the autonomy policy or create a new action.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {action.requires_owner_approval && !action.approved_at && (
            <ActionButton label="AUTHORIZE" onClick={handleApprove} busy={busy} tone="warn" />
          )}
          {!approval && (!action.requires_owner_approval || action.approved_at) && !action.started_at && (
            <ActionButton label="START" onClick={handleStart} busy={busy} />
          )}
          {approval && action.approved_at && !action.result && (
            <ActionButton label="RECORD WHAT HAPPENED" onClick={() => setShowResultForm((v) => !v)} busy={busy} />
          )}
          {!approval && action.started_at && !action.completed_at && (
            <ActionButton label="RECORD RESULT" onClick={() => setShowResultForm((v) => !v)} busy={busy} />
          )}
          {approval && action.result && action.revenue === null && (
            <ActionButton label="RECORD VERIFIED PAYMENT" onClick={() => setShowPaymentForm((v) => !v)} busy={busy} />
          )}
        </div>
      )}

      {formError && <p className="text-xs text-forge-danger mt-3">{formError}</p>}

      {showResultForm && (
        <div className="mt-4 pt-4 border-t border-forge-border space-y-2 animate-fade-up">
          <input
            className="w-full bg-forge-panel2 border border-forge-border rounded-md px-3 py-2 text-sm"
            placeholder="What actually happened? (required)"
            value={result}
            onChange={(e) => setResult(e.target.value)}
          />
          {!approval && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input
                className="bg-forge-panel2 border border-forge-border rounded-md px-3 py-2 text-sm"
                placeholder="Revenue $ (real only)"
                value={revenue}
                onChange={(e) => setRevenue(e.target.value)}
              />
              <input
                className="bg-forge-panel2 border border-forge-border rounded-md px-3 py-2 text-sm"
                placeholder="Conversions"
                value={conversions}
                onChange={(e) => setConversions(e.target.value)}
              />
              <input
                className="bg-forge-panel2 border border-forge-border rounded-md px-3 py-2 text-sm"
                placeholder="Costs $ (real only)"
                value={costs}
                onChange={(e) => setCosts(e.target.value)}
              />
            </div>
          )}
          <ActionButton label="SUBMIT RESULT" onClick={handleRecordResult} busy={busy} />
        </div>
      )}

      {showPaymentForm && (
        <div className="mt-4 pt-4 border-t border-forge-border space-y-2 animate-fade-up">
          <p className="text-xs text-neutral-500">
            Only a payment you can point at. A conversation is not revenue.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input
              className="bg-forge-panel2 border border-forge-border rounded-md px-3 py-2 text-sm"
              placeholder="Amount"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            <input
              className="bg-forge-panel2 border border-forge-border rounded-md px-3 py-2 text-sm"
              placeholder="Currency"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
            />
            <input
              className="bg-forge-panel2 border border-forge-border rounded-md px-3 py-2 text-sm"
              placeholder="Source, such as stripe"
              value={paymentSource}
              onChange={(e) => setPaymentSource(e.target.value)}
            />
            <input
              className="bg-forge-panel2 border border-forge-border rounded-md px-3 py-2 text-sm"
              placeholder="Payment reference"
              value={paymentReference}
              onChange={(e) => setPaymentReference(e.target.value)}
            />
          </div>
          <ActionButton label="SUBMIT PAYMENT" onClick={handleVerifiedPayment} busy={busy} />
        </div>
      )}
    </GlassPanel>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm font-semibold tabular text-neutral-100">{value}</p>
      <p className="text-[10px] text-neutral-500 uppercase">{label}</p>
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  busy,
  tone = "default",
}: {
  label: string;
  onClick: () => void;
  busy: boolean;
  tone?: "default" | "warn";
}) {
  return (
    <button
      disabled={busy}
      onClick={onClick}
      className={`text-xs px-3 py-1.5 rounded-md border font-medium tracking-wide disabled:opacity-50 ${
        tone === "warn"
          ? "border-forge-warn/40 text-forge-warn hover:bg-forge-warn/10"
          : "border-forge-border text-neutral-300 hover:glow-border"
      }`}
    >
      {busy ? "…" : label}
    </button>
  );
}
