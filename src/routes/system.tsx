import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Lock, Trash2 } from "lucide-react";
import { Container } from "@/components/layout/container";
import { SystemEditor } from "@/components/system/system-editor";
import { ProgressPanel } from "@/components/system/system-panels";
import { deriveStages } from "@/lib/system/paths";
import { emptyState } from "@/lib/system/state";
import { useSystemState } from "@/lib/system/use-system";

export const Route = createFileRoute("/system")({
  component: SystemPage,
  head: () => ({ meta: [{ title: "Edit personal context — Hami" }] }),
});

function SystemPage() {
  const {
    state,
    ready,
    update,
    reset,
    mode,
    guestState,
    useTemporaryContext,
    error,
    storageWarning,
    retry,
  } = useSystemState();
  const [confirming, setConfirming] = useState(false);
  const stages = deriveStages(state ?? emptyState());

  return (
    <main>
      <Container className="py-8 sm:py-10">
        <Link to="/" className="inline-flex items-center gap-1 text-sm font-bold text-accent hover:underline">
          <ArrowLeft className="size-4" aria-hidden="true" /> Back to home
        </Link>
        <h1 className="mt-4 text-[clamp(1.9rem,4vw,2.8rem)] font-black tracking-[-0.03em] text-ink">Edit personal context</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          <span className="inline-flex items-center gap-2 font-bold text-ink"><Lock className="size-4 text-accent" aria-hidden="true" />Private to you</span>
          <br />
          Hami uses what you choose to share here to understand what may help you. It is never part of public
          feed, network, or discovery projections. Nothing is published unless you explicitly authorize sharing.
          Leave anything unknown or blank.
        </p>

        {mode === "guest" ? (
          <div className="mt-5 rounded-card border border-line bg-card p-4">
            <p className="text-sm leading-6 text-muted">
              This is temporary context for this tab only. It is not sent to Hami’s server.
            </p>
            {state ? (
              <Link to="/login" className="link-arrow mt-2 inline-flex min-h-10 items-center text-sm font-bold text-accent">
                Sign in to choose what to save privately
              </Link>
            ) : null}
          </div>
        ) : guestState ? (
          <div className="mt-5 rounded-card border border-accent/50 bg-card p-4">
            <p className="text-sm leading-6 text-muted">
              Temporary context from this tab is available. It has not been uploaded. Review it before choosing
              whether to copy these fields into your private account context.
            </p>
            <button
              type="button"
              className="btn-secondary mt-3 min-h-10 rounded-card border border-line px-3 text-sm font-bold"
              onClick={useTemporaryContext}
            >
              Review temporary context
            </button>
          </div>
        ) : null}

        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <section className="card p-5 sm:p-6" aria-label="Edit your System">
            {!ready ? <p className="text-sm text-dim" role="status">Loading private context…</p> : error ? (
              <div className="grid gap-3">
                <p className="text-sm font-semibold text-danger" role="alert">{error}</p>
                <button type="button" className="btn-secondary min-h-10 w-fit rounded-card border border-line px-3 text-sm font-bold" onClick={retry}>
                  Retry
                </button>
              </div>
            ) : (
              <>
                {storageWarning ? <p className="mb-4 text-sm font-semibold text-danger" role="alert">{storageWarning}</p> : null}
                <SystemEditor state={state} onSave={update} privacyMode={mode} />
              </>
            )}
          </section>
          <div className="grid content-start gap-6">
            <ProgressPanel stages={stages} />
            <section className="card p-5" aria-label="Your data">
              <h2 className="text-sm font-extrabold text-ink">Your context</h2>
              <p className="mt-1 text-xs leading-5 text-muted">
                {mode === "account"
                  ? "Delete your private account context and temporary context in this tab."
                  : "Remove temporary context from this tab."}
              </p>
              {confirming ? (
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    className="inline-flex min-h-10 items-center gap-1 rounded-card border-2 border-danger px-3 text-sm font-bold text-danger"
                    onClick={() => {
                      void reset()
                        .then(() => setConfirming(false))
                        .catch(() => setConfirming(false));
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
                  disabled={!state && !guestState}
                >
                  <Trash2 className="size-4" aria-hidden="true" /> Clear my context
                </button>
              )}
            </section>
          </div>
        </div>
      </Container>
    </main>
  );
}
