import { useEffect, useMemo, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowRight, CalendarDays, MapPin, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/layout/container";
import {
  createBookingRequest,
  loadProviders,
  loadPublicTrust,
  type ProviderRecord,
  type PublicTrust,
} from "@/lib/content";

type ProviderSearch = { q?: string; provider?: number };

export const Route = createFileRoute("/providers")({
  validateSearch: (search: Record<string, unknown>): ProviderSearch => {
    const q = typeof search.q === "string" && search.q.trim() ? search.q.trim() : undefined;
    const raw = search.provider;
    const provider = typeof raw === "number" ? raw : typeof raw === "string" && /^\d+$/.test(raw) ? Number(raw) : undefined;
    return { q, provider: provider && provider > 0 ? provider : undefined };
  },
  component: ProvidersPage,
});

function ProvidersPage() {
  const search = Route.useSearch();
  const [query, setQuery] = useState(search.q ?? "");
  const [category, setCategory] = useState("All");
  const navigate = useNavigate();
  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  const [providerLoadState, setProviderLoadState] = useState<"loading" | "ready" | "unavailable">("loading");
  const [reloadVersion, setReloadVersion] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedListingId, setSelectedListingId] = useState<number | null>(null);
  const [booking, setBooking] = useState({
    name: "",
    phone: "",
    email: "",
    service: "",
    date: "",
    notes: "",
  });
  const [bookingStatus, setBookingStatus] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastBookingId, setLastBookingId] = useState<number | null>(null);
  const [trust, setTrust] = useState<PublicTrust | null>(null);

  useEffect(() => {
    let active = true;
    setProviderLoadState("loading");
    void loadProviders().then((loaded) => {
      if (!active) {
        return;
      }
      if (loaded === null) {
        setProviders([]);
        setProviderLoadState("unavailable");
        return;
      }
      setProviders(loaded);
      setProviderLoadState("ready");
      const requested = search.provider ? loaded.find((provider) => provider.id === search.provider) ?? null : loaded[0] ?? null;
      const firstListingId = requested?.listings[0]?.id ?? null;
      setSelectedId(requested?.id ?? null);
      setSelectedListingId(firstListingId);
    });
    return () => {
      active = false;
    };
  }, [reloadVersion, search.provider]);

  const filteredProviders = useMemo(() => {
    return providers.filter((provider) => {
      const matchesCategory = category === "All" || provider.category === category;
      const haystack = `${provider.name} ${provider.summary} ${provider.category} ${provider.location} ${provider.listings.map((listing) => `${listing.title} ${listing.description} ${listing.category ?? ""}`).join(" ")}`.toLowerCase();
      const matchesQuery = haystack.includes(query.trim().toLowerCase());
      return matchesCategory && matchesQuery;
    });
  }, [category, providers, query]);

  const categories = ["All", ...Array.from(new Set(providers.map((provider) => provider.category).filter(Boolean)))];

  const selectedProvider =
    filteredProviders.find((provider) => provider.id === selectedId) ?? filteredProviders[0] ?? providers[0] ?? null;

  useEffect(() => {
    if (!selectedProvider) {
      setSelectedListingId(null);
      return;
    }

    const validIds = selectedProvider.listings.map((listing) => listing.id);
    setSelectedListingId((current) => {
      if (current !== null && validIds.includes(current)) {
        return current;
      }
      return selectedProvider.listings[0]?.id ?? null;
    });
  }, [selectedProvider]);

  useEffect(() => {
    if (!selectedProvider) {
      setTrust(null);
      return;
    }
    let active = true;
    void loadPublicTrust("provider", selectedProvider.id).then((loaded) => {
      if (active) setTrust(loaded);
    });
    return () => {
      active = false;
    };
  }, [selectedProvider]);

  const selectedListing =
    selectedProvider?.listings.find((listing) => listing.id === selectedListingId) ?? selectedProvider?.listings[0] ?? null;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!selectedProvider) {
      setBookingStatus("Select a verified provider before submitting a booking request.");
      return;
    }

    if (!booking.name.trim()) {
      setBookingStatus("Please add your name before submitting the request.");
      return;
    }

    setIsSubmitting(true);
    setBookingStatus("Submitting your request...");

    const result = await createBookingRequest({
      provider_id: selectedProvider.id,
      service_listing_id: selectedListing?.id ?? null,
      requester_name: booking.name.trim(),
      requester_phone: booking.phone.trim() || null,
      requester_email: booking.email.trim() || null,
      requested_service: booking.service.trim() || selectedListing?.title || selectedProvider.service,
      requested_date: booking.date || null,
      requested_time: null,
      notes: booking.notes.trim() || null,
    });

    setIsSubmitting(false);

    if (!result) {
      setBookingStatus("The request was not recorded. Only a verified public provider can receive one.");
      return;
    }

    setLastBookingId(result.id);
    setBookingStatus(`Request #${result.id} is ${result.status}.`);
    await navigate({ to: "/requests/$id", params: { id: String(result.id) } });
  };

  return (
    <main className="py-10 sm:py-12">
      <Container className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <div>
            <p className="font-mono text-micro uppercase tracking-[0.14em] text-cyan">Services, one path</p>
            <h1 className="mt-2 font-display text-4xl tracking-tight text-fg">Verified services</h1>
            <p className="mt-2 max-w-xl text-sm text-muted">This list is the usable service path. It is not the whole network. A provider appears only when that record is verified and public.</p>
          </div>

          <div className="flex flex-col gap-4 rounded-2xl border border-line bg-raised p-4 sm:flex-row">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search plumbing, repair, cleaning..."
              className="min-h-12 flex-1 rounded-xl border border-line bg-void px-4 text-base text-fg placeholder:text-muted"
            />
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              className="min-h-12 rounded-xl border border-line bg-void px-4 text-base text-fg"
            >
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-4">
            {providerLoadState === "loading" ? (
              <p className="rounded-2xl border border-line bg-raised p-6 text-muted">Checking verified provider records…</p>
            ) : providerLoadState === "unavailable" ? (
              <div className="rounded-2xl border border-line bg-raised p-6 text-muted" role="alert">
                <p>The provider service is unavailable. Forge could not check the public listings, so none are being reported as missing.</p>
                <button type="button" onClick={() => setReloadVersion((version) => version + 1)} className="mt-3 min-h-10 rounded-full border border-line px-4 text-sm text-fg">Retry</button>
              </div>
            ) : filteredProviders.length > 0 ? (
              filteredProviders.map((provider) => (
                <button
                  key={provider.id}
                  type="button"
                  onClick={() => setSelectedId(provider.id)}
                  className={`w-full rounded-2xl border p-4 text-left transition ${
                    selectedProvider?.id === provider.id ? "border-cyan/40 bg-cyan-dim" : "border-line bg-raised hover:border-cyan/20"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">{provider.category}</p>
                      <h2 className="mt-2 font-display text-2xl text-fg">{provider.name}</h2>
                    </div>
                    {provider.verified && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-cyan/40 bg-void px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-cyan">
                        <ShieldCheck className="size-3" />
                        Verified
                      </span>
                    )}
                  </div>

                  <p className="mt-3 text-sm text-muted">{provider.summary}</p>

                  <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-muted">
                    <span className="inline-flex items-center gap-1"><MapPin className="size-4 text-cyan" /> {provider.location}</span>
                    <span>{provider.response}</span>
                  </div>

                  <div className="mt-4 flex items-center justify-between text-sm">
                    <span className="font-medium text-fg">{provider.price}</span>
                    <span className="inline-flex items-center gap-1 text-cyan">
                      View details <ArrowRight className="size-4" />
                    </span>
                  </div>
                </button>
              ))
            ) : (
              <div className="rounded-2xl border border-line bg-raised p-6 text-muted">
                No verified public providers match this search right now.
              </div>
            )}
          </div>
        </div>

        <aside className="rounded-[2rem] border border-line bg-raised p-5 sm:p-6">
          {selectedProvider ? (
            <>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">Selected provider</p>
                  <h2 className="mt-2 font-display text-2xl text-fg">{selectedProvider.name}</h2>
                </div>
                <span className="rounded-full border border-line bg-void px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-dim">
                  {selectedProvider.category}
                </span>
              </div>

              <div className="mt-4 space-y-3 text-sm text-muted">
                <p className="inline-flex items-center gap-2"><MapPin className="size-4 text-cyan" /> {selectedProvider.location}</p>
                <p className="inline-flex items-center gap-2"><CalendarDays className="size-4 text-cyan" /> {selectedProvider.response}</p>
                <p>Verification is the recorded check on this provider. There is no review score until completed jobs exist.</p>
              </div>

              <div className="mt-4 rounded-2xl border border-line bg-void p-4">
                <p className="font-mono text-micro uppercase tracking-[0.12em] text-cyan">Recorded trust</p>
                <p className="mt-2 text-sm text-muted">
                  {trust
                    ? `${trust.recorded_requests} request(s) recorded · ${trust.disputes} dispute(s)`
                    : "No public trust record is available for this provider."}
                </p>
                {trust?.unknowns.length ? <p className="mt-2 text-xs text-muted">{trust.unknowns.join(" · ")}</p> : null}
              </div>

              <div className="mt-5 space-y-3">
                {selectedProvider.listings.length > 0 ? (
                  selectedProvider.listings.map((listing) => (
                    <button
                      key={listing.id}
                      type="button"
                      onClick={() => setSelectedListingId(listing.id)}
                      className={`w-full rounded-2xl border p-3 text-left transition ${
                        selectedListing?.id === listing.id ? "border-cyan/40 bg-cyan-dim" : "border-line bg-void hover:border-cyan/20"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-fg">{listing.title}</p>
                        <span className="text-sm font-medium text-cyan">
                          {listing.price_from ? `${listing.price_from} ${listing.currency ?? "NPR"}` : "Price not recorded"}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-muted">{listing.description}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
                        <span>{listing.location ?? "Location pending"}</span>
                        <span>{listing.availability_status ?? "Availability not recorded"}</span>
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="rounded-2xl border border-line bg-void p-4 text-sm text-muted">
                    No public service listing is attached to this provider yet.
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-line bg-void p-4 text-sm text-muted">
              {providerLoadState === "loading"
                ? "Checking the selected provider…"
                : providerLoadState === "unavailable"
                  ? "Provider details are unavailable until the public service responds."
                  : search.provider
                ? "That provider is not on the public verified list."
                : "No verified provider is selected. Choose one from the list when a public record exists."}
            </div>
          )}

          {selectedProvider ? (
            <form onSubmit={handleSubmit} className="mt-6 space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  value={booking.name}
                  onChange={(event) => setBooking((current) => ({ ...current, name: event.target.value }))}
                  placeholder="Your name"
                  className="min-h-11 w-full rounded-xl border border-line bg-void px-3 text-sm text-fg placeholder:text-muted"
                />
                <input
                  type="tel"
                  value={booking.phone}
                  onChange={(event) => setBooking((current) => ({ ...current, phone: event.target.value }))}
                  placeholder="Phone"
                  className="min-h-11 w-full rounded-xl border border-line bg-void px-3 text-sm text-fg placeholder:text-muted"
                />
              </div>
              <input
                type="email"
                value={booking.email}
                onChange={(event) => setBooking((current) => ({ ...current, email: event.target.value }))}
                placeholder="Email"
                className="min-h-11 w-full rounded-xl border border-line bg-void px-3 text-sm text-fg placeholder:text-muted"
              />
              <input
                value={booking.service}
                onChange={(event) => setBooking((current) => ({ ...current, service: event.target.value }))}
                placeholder={selectedListing?.title ?? "Service needed"}
                className="min-h-11 w-full rounded-xl border border-line bg-void px-3 text-sm text-fg placeholder:text-muted"
              />
              <input
                type="date"
                value={booking.date}
                onChange={(event) => setBooking((current) => ({ ...current, date: event.target.value }))}
                className="min-h-11 w-full rounded-xl border border-line bg-void px-3 text-sm text-fg"
              />
              <textarea
                value={booking.notes}
                onChange={(event) => setBooking((current) => ({ ...current, notes: event.target.value }))}
                rows={4}
                placeholder="Tell the provider what you need help with"
                className="w-full rounded-xl border border-line bg-void px-3 py-2 text-sm text-fg placeholder:text-muted"
              />
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Submitting..." : "Submit booking request"}
              </Button>
              {lastBookingId ? (
                <p className="rounded-xl border border-cyan/30 bg-cyan/5 px-3 py-2 text-sm text-cyan">
                  Booking #{lastBookingId} created.
                </p>
              ) : null}
              {bookingStatus ? (
                <p className="rounded-xl border border-amber/30 bg-amber/5 px-3 py-2 text-sm text-muted">{bookingStatus}</p>
              ) : null}
            </form>
          ) : null}
        </aside>
      </Container>
    </main>
  );
}
