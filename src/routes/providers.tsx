import { useEffect, useMemo, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowRight, CalendarDays, MapPin, Search, ShieldCheck, Store } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, SkeletonCards, UnavailableState } from "@/components/ui/feedback";
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
    <main>
      <PageHeader
        eyebrow="Services, one path"
        title="Verified services"
        lede="This is the verified-service path within the network. A provider appears only when that record is verified and public."
      >
        <div className="mt-8 flex max-w-2xl flex-col gap-2 rounded-card border border-line bg-card/80 p-2 backdrop-blur sm:flex-row" role="search">
          <label className="relative flex-1">
            <span className="sr-only">Search services</span>
            <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-dim" aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search plumbing, repair, cleaning..."
              className="min-h-12 w-full rounded-card border border-transparent bg-paper pl-10 pr-4 text-base text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]"
            />
          </label>
          <label>
            <span className="sr-only">Category</span>
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              className="min-h-12 w-full rounded-card border border-transparent bg-paper px-4 text-base text-ink focus-visible:border-accent sm:w-auto"
            >
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>
      </PageHeader>

      <Container className="grid gap-8 py-10 sm:py-14 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
        <div className="space-y-3">
          {providerLoadState === "ready" && filteredProviders.length > 0 ? (
            <p className="font-mono text-micro uppercase tracking-[0.12em] text-dim" aria-live="polite">
              {filteredProviders.length} verified provider{filteredProviders.length === 1 ? "" : "s"}
            </p>
          ) : null}
          {providerLoadState === "loading" ? (
            <SkeletonCards count={3} label="Checking verified provider records…" className="space-y-3" />
          ) : providerLoadState === "unavailable" ? (
            <UnavailableState
              title="Provider service unavailable"
              body="The provider service is unavailable. Hami could not check the public listings, so none are being reported as missing."
              onRetry={() => setReloadVersion((version) => version + 1)}
            />
          ) : filteredProviders.length > 0 ? (
            filteredProviders.map((provider, index) => {
              const selected = selectedProvider?.id === provider.id;
              return (
                <button
                  key={provider.id}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setSelectedId(provider.id)}
                  className={`card card-interactive reveal block w-full p-5 text-left ${selected ? "card-accent" : ""}`}
                  style={{ "--i": Math.min(index, 8) } as React.CSSProperties}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <span className="icon-chip" aria-hidden="true">
                        <Store className="size-4" />
                      </span>
                      <div>
                        <p className="font-mono text-micro uppercase tracking-[0.12em] text-accent">{provider.category}</p>
                        <h2 className="mt-1 font-display text-2xl leading-tight tracking-tight text-ink">{provider.name}</h2>
                      </div>
                    </div>
                    {provider.verified && (
                      <span className="status-pill status-pill-success shrink-0">
                        <ShieldCheck className="size-3" aria-hidden="true" />
                        Verified
                      </span>
                    )}
                  </div>

                  <p className="mt-3 text-sm leading-6 text-muted">{provider.summary}</p>

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3 text-sm">
                    <span className="inline-flex items-center gap-1.5 text-muted"><MapPin className="size-4 text-accent" aria-hidden="true" /> {provider.location}</span>
                    <span className="text-dim">{provider.response}</span>
                    <span className="font-medium text-ink">{provider.price}</span>
                    <span className="link-arrow inline-flex items-center gap-1 font-semibold text-accent">
                      {selected ? "Selected" : "View details"} <ArrowRight className="size-4" aria-hidden="true" />
                    </span>
                  </div>
                </button>
              );
            })
          ) : (
            <EmptyState
              icon={Store}
              title="No matching verified providers"
              body="No verified public providers match this search right now. Providers appear only after verification and publication; nothing is listed to fill the space."
            />
          )}
        </div>

        <aside className="card p-5 sm:p-6 lg:sticky lg:top-[calc(var(--header-h)+1.5rem)]" aria-label="Selected provider">
          {selectedProvider ? (
            <div className="fade-in" key={selectedProvider.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-mono text-micro uppercase tracking-[0.12em] text-accent">Selected provider</p>
                  <h2 className="mt-2 font-display text-3xl leading-tight tracking-tight text-ink">{selectedProvider.name}</h2>
                </div>
                <span className="status-pill status-pill-neutral">
                  {selectedProvider.category}
                </span>
              </div>

              <div className="mt-4 space-y-2 text-sm text-muted">
                <p className="flex items-center gap-2"><MapPin className="size-4 text-accent" aria-hidden="true" /> {selectedProvider.location}</p>
                <p className="flex items-center gap-2"><CalendarDays className="size-4 text-accent" aria-hidden="true" /> {selectedProvider.response}</p>
                <p className="pt-1 text-xs leading-5 text-dim">Verification is the recorded check on this provider. There is no review score until completed jobs exist.</p>
              </div>

              <div className="mt-5 rounded-card border border-line bg-paper/70 p-4">
                <p className="flex items-center gap-2 font-mono text-micro uppercase tracking-[0.12em] text-accent"><ShieldCheck className="size-3.5" aria-hidden="true" /> Recorded trust</p>
                <p className="mt-2 text-sm text-muted">
                  {trust
                    ? `${trust.recorded_requests} request(s) recorded · ${trust.disputes} dispute(s)`
                    : "No public trust record is available for this provider."}
                </p>
                {trust?.unknowns.length ? <p className="mt-2 text-xs text-dim">{trust.unknowns.join(" · ")}</p> : null}
              </div>

              <h3 className="mt-6 font-mono text-micro uppercase tracking-[0.12em] text-dim">Services</h3>
              <div className="mt-2 space-y-2">
                {selectedProvider.listings.length > 0 ? (
                  selectedProvider.listings.map((listing) => (
                    <button
                      key={listing.id}
                      type="button"
                      aria-pressed={selectedListing?.id === listing.id}
                      onClick={() => setSelectedListingId(listing.id)}
                      className={`w-full rounded-card border p-3 text-left transition-colors ${
                        selectedListing?.id === listing.id ? "border-accent/60 bg-accent/10" : "border-line bg-paper/60 hover:border-accent/40"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-ink">{listing.title}</p>
                        <span className="shrink-0 text-sm font-medium text-accent">
                          {listing.price_from ? `${listing.price_from} ${listing.currency ?? "NPR"}` : "Price not recorded"}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm text-muted">{listing.description}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-dim">
                        <span>{listing.location ?? "Location pending"}</span>
                        <span>{listing.availability_status ?? "Availability not recorded"}</span>
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="rounded-card border border-line bg-paper/60 p-4 text-sm text-muted">
                    No public service listing is attached to this provider yet.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="py-6 text-center">
              <span className="icon-chip mx-auto" aria-hidden="true"><Store className="size-4" /></span>
              <p className="mx-auto mt-4 max-w-xs text-sm leading-6 text-muted">
                {providerLoadState === "loading"
                  ? "Checking the selected provider…"
                  : providerLoadState === "unavailable"
                    ? "Provider details are unavailable until the public service responds."
                    : search.provider
                  ? "That provider is not on the public verified list."
                  : "No verified provider is selected. Choose one from the list when a public record exists."}
              </p>
            </div>
          )}

          {selectedProvider ? (
            <form onSubmit={handleSubmit} className="mt-6 space-y-3 border-t border-line pt-6">
              <h3 className="font-display text-2xl tracking-tight text-ink">Request this service</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block font-mono text-micro uppercase tracking-[0.1em] text-dim">Your name</span>
                  <input
                    value={booking.name}
                    onChange={(event) => setBooking((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Your name"
                    autoComplete="name"
                    className="min-h-11 w-full rounded-card border border-line bg-paper px-3 text-sm text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block font-mono text-micro uppercase tracking-[0.1em] text-dim">Phone</span>
                  <input
                    type="tel"
                    value={booking.phone}
                    onChange={(event) => setBooking((current) => ({ ...current, phone: event.target.value }))}
                    placeholder="Phone"
                    autoComplete="tel"
                    className="min-h-11 w-full rounded-card border border-line bg-paper px-3 text-sm text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]"
                  />
                </label>
              </div>
              <label className="block">
                <span className="mb-1.5 block font-mono text-micro uppercase tracking-[0.1em] text-dim">Email</span>
                <input
                  type="email"
                  value={booking.email}
                  onChange={(event) => setBooking((current) => ({ ...current, email: event.target.value }))}
                  placeholder="Email"
                  autoComplete="email"
                  className="min-h-11 w-full rounded-card border border-line bg-paper px-3 text-sm text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]"
                />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block font-mono text-micro uppercase tracking-[0.1em] text-dim">Service</span>
                  <input
                    value={booking.service}
                    onChange={(event) => setBooking((current) => ({ ...current, service: event.target.value }))}
                    placeholder={selectedListing?.title ?? "Service needed"}
                    className="min-h-11 w-full rounded-card border border-line bg-paper px-3 text-sm text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block font-mono text-micro uppercase tracking-[0.1em] text-dim">Preferred date</span>
                  <input
                    type="date"
                    value={booking.date}
                    onChange={(event) => setBooking((current) => ({ ...current, date: event.target.value }))}
                    className="min-h-11 w-full rounded-card border border-line bg-paper px-3 text-sm text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)] [color-scheme:dark]"
                  />
                </label>
              </div>
              <label className="block">
                <span className="mb-1.5 block font-mono text-micro uppercase tracking-[0.1em] text-dim">Notes</span>
                <textarea
                  value={booking.notes}
                  onChange={(event) => setBooking((current) => ({ ...current, notes: event.target.value }))}
                  rows={4}
                  placeholder="Tell the provider what you need help with"
                  className="w-full rounded-card border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-dim transition-[border-color,box-shadow] focus-visible:border-accent focus-visible:shadow-[var(--shadow-glow)]"
                />
              </label>
              <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Submitting..." : "Submit booking request"}
              </Button>
              {lastBookingId ? (
                <p role="status" className="rounded-card border border-success/35 bg-success/10 px-3 py-2 text-sm text-success">
                  Booking #{lastBookingId} created.
                </p>
              ) : null}
              {bookingStatus ? (
                <p role="status" className="rounded-card border border-warning/35 bg-warning/5 px-3 py-2 text-sm text-muted">{bookingStatus}</p>
              ) : null}
            </form>
          ) : null}
        </aside>
      </Container>
    </main>
  );
}
