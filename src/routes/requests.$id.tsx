import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, CalendarDays, CheckCircle2, Circle, Clock3, MessageSquare, SearchX } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, Skeleton, UnavailableState } from "@/components/ui/feedback";
import { getBookingRequestStatus, type BookingStatus } from "@/lib/content";

export const Route = createFileRoute("/requests/$id")({
  component: RequestStatusPage,
});

function RequestStatusPage() {
  const { id } = Route.useParams();
  const [record, setRecord] = useState<BookingStatus | null>(null);
  // invalidId: the URL segment cannot be a request number (nothing to fetch).
  // loadFailed: the fetch returned nothing. getBookingRequestStatus conflates
  // "no such request" (404) with "network failed", so nothing is inferred and
  // the requester can retry instead of being told "not on record" wrongly.
  const [invalidId, setInvalidId] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const bookingId = Number(id);
    if (!Number.isInteger(bookingId) || bookingId <= 0) {
      setInvalidId(true);
      setLoadFailed(false);
      return;
    }
    setInvalidId(false);
    setLoadFailed(false);
    setRecord(null);
    let active = true;
    void getBookingRequestStatus(bookingId).then((loaded) => {
      if (!active) return;
      if (!loaded) setLoadFailed(true);
      else setRecord(loaded);
    });
    return () => {
      active = false;
    };
  }, [id, retryKey]);

  const steps = record
    ? [
        { label: "Request stored", done: true, note: `Request #${record.id} is on record.` },
        {
          label: "Provider reply",
          done: Boolean(record.provider_response),
          note: record.provider_response ? "The provider wrote a reply." : "Waiting for the provider to write a reply.",
        },
        {
          label: "Accepted",
          done: record.status === "accepted" || record.status === "completed",
          note: "Only the provider can accept. Pending is not accepted.",
        },
      ]
    : [];

  return (
    <main>
      <PageHeader
        eyebrow="Request status"
        title="What has actually happened"
        containerClassName="max-w-3xl"
      />
      <Container className="max-w-3xl py-10 sm:py-14">
        {invalidId ? (
          <EmptyState
            icon={SearchX}
            title="No request found"
            body="No request with this number is on record."
          >
            <Link to="/providers" className="link-arrow inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-accent">
              <ArrowLeft className="size-4" aria-hidden="true" /> Back to providers
            </Link>
          </EmptyState>
        ) : loadFailed ? (
          <>
            <UnavailableState
              title="The request could not be loaded"
              body="Either request number is not on record, or the connection failed — nothing has been inferred. Try again to check."
              onRetry={() => setRetryKey((key) => key + 1)}
            />
            <div className="mt-6 text-center">
              <Link to="/providers" className="link-arrow inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-accent">
                <ArrowLeft className="size-4" aria-hidden="true" /> Back to providers
              </Link>
            </div>
          </>
        ) : !record ? (
          <div role="status" className="card p-6">
            <span className="sr-only">Checking the recorded status…</span>
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-4 h-7 w-2/3" />
            <Skeleton className="mt-6 h-3 w-full" />
            <Skeleton className="mt-2 h-3 w-4/5" />
          </div>
        ) : (
          <article className="card fade-in overflow-hidden">
            <div className="border-b border-line p-6 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-dim">Request #{record.id}</p>
                <span className={`status-pill ${record.status === "pending" ? "status-pill-warning" : "status-pill-accent"}`}>
                  <Clock3 className="size-3" aria-hidden="true" /> {record.status}
                </span>
              </div>
              <h2 className="mt-3 font-display text-4xl leading-tight tracking-tight text-ink">{record.requested_service}</h2>
              <p className="mt-2 text-sm text-muted">
                Status: <span className="text-ink">{record.status}</span>
                {record.provider_name ? ` · ${record.provider_name}` : ""}
              </p>
            </div>

            <ol className="grid gap-px bg-line sm:grid-cols-3" aria-label="Request progress">
              {steps.map((step) => (
                <li key={step.label} className="bg-card p-5">
                  <p className={`flex items-center gap-2 text-sm font-semibold ${step.done ? "text-success" : "text-muted"}`}>
                    {step.done ? <CheckCircle2 className="size-4" aria-hidden="true" /> : <Circle className="size-4" aria-hidden="true" />}
                    {step.label}
                    <span className="sr-only">{step.done ? "(done)" : "(not yet)"}</span>
                  </p>
                  <p className="mt-2 text-xs leading-5 text-dim">{step.note}</p>
                </li>
              ))}
            </ol>

            <div className="space-y-4 p-6 sm:p-8">
              <p className="flex items-start gap-3 text-sm text-muted">
                <CalendarDays className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
                <span>
                  {record.requested_date ? `Requested date: ${record.requested_date}` : "No date was recorded."}
                  {record.requested_time ? ` at ${record.requested_time}` : ""}
                </span>
              </p>
              <p className="flex items-start gap-3 text-sm text-muted">
                <MessageSquare className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
                <span>
                  {record.provider_response
                    ? `Provider reply: ${record.provider_response}`
                    : "The provider has not written a reply yet. Pending means the request was stored, not that it was accepted."}
                </span>
              </p>
              <Link to="/providers" className="link-arrow inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-accent">
                <ArrowLeft className="size-4" aria-hidden="true" /> Back to providers
              </Link>
            </div>
          </article>
        )}
      </Container>
    </main>
  );
}
