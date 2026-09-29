import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { getBookingRequestStatus, type BookingStatus } from "@/lib/content";

export const Route = createFileRoute("/requests/$id")({
  component: RequestStatusPage,
});

function RequestStatusPage() {
  const { id } = Route.useParams();
  const [record, setRecord] = useState<BookingStatus | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    const bookingId = Number(id);
    if (!Number.isInteger(bookingId) || bookingId <= 0) {
      setMissing(true);
      return;
    }
    let active = true;
    void getBookingRequestStatus(bookingId).then((loaded) => {
      if (!active) return;
      if (!loaded) setMissing(true);
      else setRecord(loaded);
    });
    return () => {
      active = false;
    };
  }, [id]);

  return (
    <main className="py-10 sm:py-14">
      <Container className="max-w-2xl">
        <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Request status</p>
        <h1 className="mt-2 font-display text-4xl tracking-tight text-fg">What has actually happened</h1>
        {missing ? (
          <p className="mt-6 rounded-2xl border border-line bg-raised p-5 text-muted">
            No request with this number is on record.
          </p>
        ) : !record ? (
          <p className="mt-6 text-muted">Checking the recorded status…</p>
        ) : (
          <div className="mt-6 space-y-4 rounded-card border border-line bg-raised p-6">
            <p className="font-mono text-micro uppercase tracking-[0.12em] text-dim">Request #{record.id}</p>
            <h2 className="font-display text-2xl text-fg">{record.requested_service}</h2>
            <p className="text-sm text-muted">
              Status: <span className="text-fg">{record.status}</span>
              {record.provider_name ? ` · ${record.provider_name}` : ""}
            </p>
            <p className="text-sm text-muted">
              {record.requested_date ? `Requested date: ${record.requested_date}` : "No date was recorded."}
              {record.requested_time ? ` at ${record.requested_time}` : ""}
            </p>
            <p className="text-sm text-muted">
              {record.provider_response
                ? `Provider reply: ${record.provider_response}`
                : "The provider has not written a reply yet. Pending means the request was stored, not that it was accepted."}
            </p>
            <Link to="/providers" className="inline-flex min-h-11 items-center text-sm text-cyan">
              Back to providers
            </Link>
          </div>
        )}
      </Container>
    </main>
  );
}
