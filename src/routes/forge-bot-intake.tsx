import { useEffect, useState, type FormEvent } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight, CalendarDays, Mail, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Container } from "@/components/layout/container";

type ForgeBotConfig = {
  intake_enabled: boolean;
  contact_email: string;
  booking_url: string;
  consent_version: string;
};

type IntakeForm = {
  email: string;
  phone: string;
  preferredChannel: "email" | "phone";
  destination: string;
  course: string;
  timeline: string;
  budgetMinimum: string;
  budgetMaximum: string;
  consentGranted: boolean;
  website: string;
};

type Receipt = {
  reference: string;
  manage_token: string;
  message: string;
};

const initialForm: IntakeForm = {
  email: "",
  phone: "",
  preferredChannel: "email",
  destination: "",
  course: "",
  timeline: "",
  budgetMinimum: "",
  budgetMaximum: "",
  consentGranted: false,
  website: "",
};

export const Route = createFileRoute("/forge-bot-intake")({
  component: ForgeBotIntakePage,
  head: () => ({
    meta: [
      { title: "Forge Bot inquiry — Hami" },
      { name: "description", content: "A consent-scoped request for Hami to review." },
      { name: "robots", content: "noindex,nofollow" },
    ],
  }),
});

function ForgeBotIntakePage() {
  const [config, setConfig] = useState<ForgeBotConfig | null>(null);
  const [configError, setConfigError] = useState("");
  const [form, setForm] = useState<IntakeForm>(initialForm);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void fetch("/api/forge-bot/config")
      .then(async (response) => {
        if (!response.ok) throw new Error(`Configuration request failed (${response.status}).`);
        return (await response.json()) as ForgeBotConfig;
      })
      .then((result) => {
        if (active) setConfig(result);
      })
      .catch((cause: unknown) => {
        if (active) {
          setConfigError(
            cause instanceof Error ? cause.message : "Forge Bot configuration is unavailable.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  function update<K extends keyof IntakeForm>(key: K, value: IntakeForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!config?.intake_enabled) {
      setError("Web intake is not open yet. Please use the contact email below.");
      return;
    }
    if (form.budgetMaximum && Number(form.budgetMaximum) < Number(form.budgetMinimum)) {
      setError("The maximum budget must be at least the minimum.");
      return;
    }
    setBusy(true);
    setError("");
    setReceipt(null);
    try {
      const response = await fetch("/api/forge-bot/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email || null,
          phone: form.phone || null,
          preferred_channel: form.preferredChannel,
          destination: form.destination,
          course: form.course,
          timeline: form.timeline,
          budget_minimum: Number(form.budgetMinimum),
          budget_maximum: Number(form.budgetMaximum),
          consent_granted: form.consentGranted,
          website: form.website,
        }),
      });
      const result: unknown = await response.json();
      if (!response.ok) {
        const message =
          typeof result === "object" &&
          result !== null &&
          "detail" in result &&
          typeof result.detail === "string"
            ? result.detail
            : `Request failed (${response.status}).`;
        throw new Error(message);
      }
      setReceipt(result as Receipt);
      setForm(initialForm);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "The request could not be submitted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <Container className="py-12 sm:py-16">
        <div className="max-w-3xl">
          <p className="font-mono text-xs font-bold uppercase tracking-[0.18em] text-accent">
            Forge Bot · Inquiry
          </p>
          <h1 className="mt-3 text-title">A clear request, for owner review.</h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted">
            Share only what is needed to understand this request. The fields
            capture stated answers; they do not establish eligibility, admission,
            a visa, employment, or any outcome.
          </p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <a
            href={config?.contact_email ? `mailto:${config.contact_email}` : undefined}
            className="flex min-h-20 items-center gap-3 border-2 border-line bg-card p-4 text-ink hover:border-accent"
          >
            <Mail className="size-5 text-accent" aria-hidden="true" />
            <span>
              <span className="block text-xs uppercase tracking-wide text-muted">Contact email</span>
              <span className="mt-1 block font-bold">
                {config?.contact_email ?? "Loading contact details"}
              </span>
            </span>
          </a>
          <a
            href={config?.booking_url}
            target="_blank"
            rel="noreferrer"
            className="flex min-h-20 items-center gap-3 border-2 border-line bg-card p-4 text-ink hover:border-accent"
          >
            <CalendarDays className="size-5 text-accent" aria-hidden="true" />
            <span>
              <span className="block text-xs uppercase tracking-wide text-muted">Booking link</span>
              <span className="mt-1 block font-bold">Choose a time with Hami</span>
            </span>
          </a>
        </div>

        {configError ? (
          <p className="mt-6 border border-danger/50 bg-card p-4 text-sm text-danger" role="alert">
            {configError}
          </p>
        ) : null}

        {!config?.intake_enabled ? (
          <section className="mt-8 max-w-3xl border-2 border-line bg-card p-5 sm:p-7">
            <h2 className="text-lg font-extrabold">Online intake is not open yet</h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              The form remains disabled until Hami finishes its local pilot and
              abuse-control checks. You can use the contact email or booking
              link above; neither action sends a message automatically.
            </p>
          </section>
        ) : receipt ? (
          <section className="mt-8 max-w-3xl border-2 border-accent/60 bg-card p-5 sm:p-7" role="status">
            <div className="flex items-center gap-2 text-accent">
              <ShieldCheck className="size-5" aria-hidden="true" />
              <h2 className="text-lg font-extrabold text-ink">Request received for review</h2>
            </div>
            <p className="mt-3 text-sm leading-6 text-muted">
              Reference: <span className="font-mono text-ink">{receipt.reference}</span>.
              No automated response or booking was sent. This request is not
              counted as a customer or revenue outcome.
            </p>
            <div className="mt-4 border border-line bg-paper p-4">
              <Label htmlFor="manage-token">Private one-time control code</Label>
              <Input id="manage-token" readOnly value={receipt.manage_token} />
              <p className="mt-2 text-xs leading-5 text-muted">
                Keep this code private. It can permanently opt out and erase
                this inquiry's details. A duplicate submission may receive a
                code that does not control an existing record. On opt-out,
                Hami retains HMAC-only suppression tokens to prevent re-entry.
              </p>
            </div>
            <Button
              className="mt-5"
              type="button"
              variant="secondary"
              onClick={() => {
                setReceipt(null);
                setForm(initialForm);
              }}
            >
              Submit another inquiry
              <ArrowRight aria-hidden="true" />
            </Button>
          </section>
        ) : (
          <section className="mt-8 max-w-3xl border-2 border-line bg-card p-5 sm:p-7">
            <h2 className="text-lg font-extrabold">Share the basics</h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              Contact information and answers are stored only in the Forge Bot
              lead record. They are not added to public feed, discovery, or
              opportunity projections.
            </p>

            <form className="mt-6 grid gap-5" onSubmit={submit}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="destination">Destination</Label>
                  <Input
                    id="destination"
                    maxLength={120}
                    required
                    value={form.destination}
                    onChange={(event) => update("destination", event.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="course">Course or field</Label>
                  <Input
                    id="course"
                    maxLength={160}
                    required
                    value={form.course}
                    onChange={(event) => update("course", event.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="timeline">Expected start timeline</Label>
                  <Input
                    id="timeline"
                    maxLength={120}
                    required
                    value={form.timeline}
                    onChange={(event) => update("timeline", event.target.value)}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="budget-minimum">Budget min. (NPR)</Label>
                    <Input
                      id="budget-minimum"
                      type="number"
                      min="0"
                      max="1000000000000"
                      required
                      value={form.budgetMinimum}
                      onChange={(event) => update("budgetMinimum", event.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="budget-maximum">Budget max. (NPR)</Label>
                    <Input
                      id="budget-maximum"
                      type="number"
                      min="0"
                      max="1000000000000"
                      required
                      value={form.budgetMaximum}
                      onChange={(event) => update("budgetMaximum", event.target.value)}
                    />
                  </div>
                </div>
              </div>

              <fieldset className="grid gap-4 border-t border-line pt-5 sm:grid-cols-2">
                <legend className="px-1 text-sm font-bold">How may Hami reply?</legend>
                <div>
                  <Label htmlFor="lead-email">Email</Label>
                  <Input
                    id="lead-email"
                    type="email"
                    autoComplete="email"
                    maxLength={254}
                    required={form.preferredChannel === "email"}
                    value={form.email}
                    onChange={(event) => update("email", event.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="lead-phone">Phone (optional alternative)</Label>
                  <Input
                    id="lead-phone"
                    type="tel"
                    autoComplete="tel"
                    maxLength={64}
                    required={form.preferredChannel === "phone"}
                    value={form.phone}
                    onChange={(event) => update("phone", event.target.value)}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="preferred-channel">Preferred reply channel</Label>
                  <select
                    id="preferred-channel"
                    className="h-11 w-full rounded-card border border-line bg-paper px-3 text-sm text-ink"
                    value={form.preferredChannel}
                    onChange={(event) =>
                      update("preferredChannel", event.target.value as "email" | "phone")
                    }
                  >
                    <option value="email">Email</option>
                    <option value="phone">Phone</option>
                  </select>
                </div>
              </fieldset>

              <div className="hidden" aria-hidden="true">
                <Label htmlFor="website">Leave this field empty</Label>
                <Input
                  id="website"
                  tabIndex={-1}
                  autoComplete="off"
                  value={form.website}
                  onChange={(event) => update("website", event.target.value)}
                />
              </div>

              <label className="flex items-start gap-3 border border-line p-4 text-sm leading-6 text-muted">
                <input
                  className="mt-1 size-4 accent-[var(--color-accent)]"
                  type="checkbox"
                  required
                  checked={form.consentGranted}
                  onChange={(event) => update("consentGranted", event.target.checked)}
                />
                <span>
                  I agree that Hami may use these details only to review and
                  respond to this inquiry on my selected channel. This is not
                  marketing consent. I can permanently opt out and erase the
                  inquiry with the private control code shown after submission.
                </span>
              </label>

              {error ? (
                <p className="text-sm font-semibold text-danger" role="alert">{error}</p>
              ) : null}
              <p className="text-xs leading-5 text-muted">
                Do not include passport numbers, identity documents, academic
                records, or other sensitive documents. No admission, visa, or
                employment outcome is promised. An owner reviews submissions;
                no email or message is sent automatically. No time-based
                retention period is configured; records remain until erased.
              </p>
              <Button type="submit" disabled={busy}>
                {busy ? "Submitting…" : "Send for owner review"}
                <ArrowRight aria-hidden="true" />
              </Button>
            </form>
          </section>
        )}
      </Container>
    </main>
  );
}
