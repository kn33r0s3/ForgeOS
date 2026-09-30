import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Trash2 } from "lucide-react";
import { Container } from "@/components/layout/container";
import { SystemEditor } from "@/components/system/system-editor";
import { ProgressPanel } from "@/components/system/system-panels";
import { deriveStages } from "@/lib/system/paths";
import { emptyState } from "@/lib/system/state";
import { useSystemState } from "@/lib/system/use-system";

export const Route = createFileRoute("/system")({
  component: SystemPage,
  head: () => ({ meta: [{ title: "Your System — Hami" }] }),
});

function SystemPage() {
  const { state, ready, update, reset } = useSystemState();
  const [confirming, setConfirming] = useState(false);
  const stages = deriveStages(state ?? emptyState());

  return (
    <main>
      <Container className="py-8 sm:py-10">
        <Link to="/" className="inline-flex items-center gap-1 text-sm font-bold text-accent hover:underline">
          <ArrowLeft className="size-4" aria-hidden="true" /> Back to your System
        </Link>
        <h1 className="mt-4 text-[clamp(1.9rem,4vw,2.8rem)] font-black tracking-[-0.03em] text-ink">Your gear</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          The more specific you are, the more useful connections Hami can find. You own this: it lives on
          this device, is labelled as stated by you, and is never published.
        </p>

        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <section className="card p-5 sm:p-6" aria-label="Edit your System">
            {ready ? <SystemEditor state={state} onSave={update} /> : <p className="text-sm text-dim">Loading…</p>}
          </section>
          <div className="grid content-start gap-6">
            <ProgressPanel stages={stages} />
            <section className="card p-5" aria-label="Your data">
              <h2 className="text-sm font-extrabold text-ink">Your data</h2>
              <p className="mt-1 text-xs leading-5 text-muted">
                Remove everything Hami knows about you on this device.
              </p>
              {confirming ? (
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    className="inline-flex min-h-10 items-center gap-1 rounded-card border-2 border-danger px-3 text-sm font-bold text-danger"
                    onClick={() => {
                      reset();
                      setConfirming(false);
                    }}
                  >
                    <Trash2 className="size-4" aria-hidden="true" /> Yes, clear it
                  </button>
                  <button
                    type="button"
                    className="min-h-10 rounded-card border-2 border-line px-3 text-sm font-bold text-muted"
                    onClick={() => setConfirming(false)}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="mt-3 inline-flex min-h-10 items-center gap-1 rounded-card border-2 border-line px-3 text-sm font-bold text-muted hover:border-danger hover:text-danger"
                  onClick={() => setConfirming(true)}
                  disabled={!state}
                >
                  <Trash2 className="size-4" aria-hidden="true" /> Clear my System
                </button>
              )}
            </section>
          </div>
        </div>
      </Container>
    </main>
  );
}
