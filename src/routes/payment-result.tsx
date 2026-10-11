import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { clearStoredCheckoutAttempt } from "@/lib/checkout-attempt-storage";

type PaymentIntentStatus = {
  intent: string;
  provider: "esewa" | "khalti";
  status: "CREATED" | "INITIATED" | "PENDING" | "VERIFIED" | "FAILED" | "CANCELLED" | "DISPUTED" | "REFUNDED";
  amount_paisa: number;
  amount_npr: string;
  currency: "NPR";
  product_name: string;
  fulfilled: boolean;
  offer_id: number;
  retry_allowed?: boolean;
  recovery?: {
    checked: boolean;
    retry_allowed: boolean;
    provider_status?: string | null;
    message: string;
  };
};

export const Route = createFileRoute("/payment-result")({
  validateSearch: (search: Record<string, unknown>) => ({
    intent: typeof search.intent === "string" ? search.intent : "",
  }),
  head: () => ({
    meta: [
      { title: "Payment status · Hami" },
      { name: "robots", content: "noindex,nofollow,noarchive" },
    ],
  }),
  component: PaymentResultPage,
});

function PaymentResultPage() {
  const { intent } = Route.useSearch();
  const [record, setRecord] = useState<PaymentIntentStatus | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);
  const [recoveryBusy, setRecoveryBusy] = useState(false);
  const [recoveryMessage, setRecoveryMessage] = useState("");
  const [retryAllowed, setRetryAllowed] = useState(false);


  useEffect(() => {
    let current = true;
    if (!intent) {
      setError("This payment link is incomplete. Return to Hami and open checkout again if needed.");
      return () => { current = false; };
    }
    setBusy(true);
    setError("");
    fetch("/api/payments/intent/" + encodeURIComponent(intent), {
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (!response.ok || !body) {
          throw new Error(body && typeof body.detail === "string" ? body.detail : "Payment status is not available.");
        }
        return body as PaymentIntentStatus;
      })
      .then((body) => { if (current) setRecord(body); })
      .catch((cause) => { if (current) setError(cause instanceof Error ? cause.message : "Payment status is not available."); })
      .finally(() => { if (current) setBusy(false); });
    return () => { current = false; };
  }, [intent, refreshCount]);

  async function confirmProviderStatus() {
    if (!intent || recoveryBusy) return;
    setRecoveryBusy(true);
    setRecoveryMessage("");
    setRetryAllowed(false);
    try {
      const response = await fetch("/api/payments/intent/" + encodeURIComponent(intent) + "/reconcile", {
        method: "POST",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      const body = await response.json().catch(() => null);
      if (!response.ok || !body) {
        throw new Error(body && typeof body.detail === "string"
          ? body.detail
          : "The provider could not confirm a safe retry. Keep the existing attempt.");
      }
      const payload = body as PaymentIntentStatus;
      setRecord(payload);
      const recovery = payload.recovery;
      if (!recovery) throw new Error("Hami did not receive a provider reconciliation result.");
      const allowed = payload.retry_allowed === true && recovery.retry_allowed === true;
      if (allowed && !clearStoredCheckoutAttempt(payload.offer_id)) {
        setRecoveryMessage("The provider confirmed the previous attempt ended, but this tab could not clear the saved attempt key. No new attempt was started.");
        return;
      }
      setRetryAllowed(allowed);
      setRecoveryMessage(recovery.message);
    } catch (cause) {
      setRecoveryMessage(cause instanceof Error ? cause.message : "The provider could not confirm a safe retry.");
    } finally {
      setRecoveryBusy(false);
    }
  }

  const isVerified = record?.status === "VERIFIED";
  const isFulfilled = isVerified && record?.fulfilled === true;
  const isPending = !!record && ["CREATED", "INITIATED", "PENDING"].includes(record.status);
  const canCheckProvider = !!record && !isVerified && !retryAllowed && ["CREATED", "INITIATED", "PENDING", "FAILED", "CANCELLED"].includes(record.status);

  return (
    <main className="flex-1 bg-background text-ink">
      <Container className="py-12 sm:py-16">
        <div className="mx-auto max-w-2xl rounded-card border-2 border-line bg-card p-5 sm:p-8">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted">Payment result</p>
          <h1 className="mt-3 font-display text-3xl font-extrabold tracking-tight">
            {isFulfilled ? "Payment and fulfillment confirmed" : isVerified ? "Payment verified; fulfillment pending" : isPending ? "Payment confirmation pending" : record ? "Payment not verified" : "Checking payment status"}
          </h1>
          {busy && !record ? <p className="mt-4 text-sm text-muted">Checking the transaction status with Hami’s payment ledger…</p> : null}
          {record ? (
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-muted">Offer</dt><dd className="mt-1 font-bold">{record.product_name}</dd></div>
              <div><dt className="text-muted">Amount</dt><dd className="mt-1 font-bold">NPR {record.amount_npr}</dd></div>
              <div><dt className="text-muted">Provider</dt><dd className="mt-1 font-bold">{record.provider === "esewa" ? "eSewa" : "Khalti"}</dd></div>
              <div><dt className="text-muted">Ledger state</dt><dd className="mt-1 font-mono font-bold">{record.status}</dd></div>
            </dl>
          ) : null}
          {isVerified ? (
            <p className="mt-5 rounded-card border border-line p-3 text-sm leading-6">
              {isFulfilled
                ? "The provider lookup verified payment and an owner confirmed fulfillment. The linked REAL revenue outcome and paid-customer event have been recorded."
                : "The provider lookup verified payment, but fulfillment is awaiting owner confirmation. This payment is not yet recorded as realized revenue."}
            </p>
          ) : isPending ? (
            <p className="mt-5 rounded-card border border-line p-3 text-sm leading-6">
              The provider has not yet supplied a confirmed payment result. This is not recorded as revenue. Refresh status after a short wait.
            </p>
          ) : record ? (
            <p className="mt-5 rounded-card border border-line p-3 text-sm leading-6">
              Hami could not verify this payment as completed. No verified revenue was recorded from this status.
            </p>
          ) : null}
          {error ? <p role="alert" className="mt-4 rounded-card border border-danger/60 p-3 text-sm">{error}</p> : null}
          {recoveryMessage ? (
            <p role={retryAllowed ? "status" : "alert"} className="mt-4 rounded-card border border-line p-3 text-sm leading-6">
              {recoveryMessage}
            </p>
          ) : null}
          {retryAllowed ? (
            <p className="mt-3 text-sm leading-6 text-muted">
              The previous attempt identity has been cleared from this tab. Return to Hami to begin a new checkout attempt; this status check did not initiate another payment.
            </p>
          ) : null}

          <div className="mt-6 flex flex-wrap gap-3">
            {canCheckProvider ? (
              <button
                type="button"
                disabled={busy || recoveryBusy}
                onClick={() => void confirmProviderStatus()}
                className="min-h-10 rounded-card border-2 border-accent px-4 py-2 text-sm font-bold text-accent disabled:opacity-60"
              >
                {recoveryBusy ? "Checking provider…" : "Check with provider before retrying"}
              </button>
            ) : null}

            <button
              type="button"
              disabled={busy || !intent}
              onClick={() => { setRecord(null); setRefreshCount((count) => count + 1); }}
              className="min-h-10 rounded-card border-2 border-accent px-4 py-2 text-sm font-bold text-accent disabled:opacity-60"
            >
              Refresh payment status
            </button>
            <Link to="/" className="inline-flex min-h-10 items-center rounded-card border border-line px-4 py-2 text-sm font-bold">
              Return to Hami
            </Link>
          </div>
          <p className="mt-5 text-xs leading-5 text-muted">
            Payment status pages contain a private transaction reference. Do not share this URL publicly.
          </p>
        </div>
      </Container>
    </main>
  );
}
