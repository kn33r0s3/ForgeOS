import { FormEvent, useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Download, FlaskConical, Plus, Timer, Trash2 } from "lucide-react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import {
  formatDuration,
  normalizeInquiry,
  parseOrderValue,
  summarizeWeek,
  weekSummaryText,
  type Channel,
  type Inquiry,
  type Outcome,
} from "@/lib/prototype-inbox";

export const Route = createFileRoute("/prototype/inbox")({
  component: InboxPrototype,
  head: () => ({ meta: [{ title: "Inquiry inbox prototype — Hami" }] }),
});

const STORAGE_KEY = "hami-prototype-inbox-v1";
type Language = "en" | "ne";

const COPY = {
  en: {
    eyebrow: "Hami · browser-only prototype",
    title: "Inquiry inbox",
    lede: "A simple one-week log for a social seller. It does not read or send messages.",
    privacy: "Everything stays in this browser. No account, no server sync, no outbound messages. Export contains totals only.",
    summary: "This week",
    inquiries: "Inquiries received",
    average: "Average reply time",
    recovered: "Recovered sales",
    lost: "Lost",
    export: "Export week summary",
    formTitle: "Add an inquiry",
    name: "Customer name",
    channel: "Channel",
    asked: "What did they ask?",
    add: "Add inquiry",
    noInquiries: "No inquiries yet",
    noInquiriesDetail: "Add the first message you need to remember. Nothing leaves this phone.",
    received: "Received",
    waiting: "Waiting",
    repliedIn: "Replied in",
    markReplied: "Mark replied",
    markRecovered: "Recovered",
    markLost: "Lost",
    amount: "Sale amount (NPR)",
    saveRecovered: "Save recovered sale",
    cancel: "Cancel",
    clear: "Clear all local data",
    remove: "Remove inquiry",
    npr: "NPR",
  },
  ne: {
    eyebrow: "Hami · ब्राउजरमा मात्र रहने नमुना",
    title: "सोधपुछ इनबक्स",
    lede: "सामाजिक सञ्जाल विक्रेताका लागि एक हप्ताको सरल लग। यसले सन्देश पढ्दैन वा पठाउँदैन।",
    privacy: "सबै कुरा यही ब्राउजरमा रहन्छ। खाता छैन, सर्भरमा पठाइँदैन, बाहिर सन्देश जाँदैन। निर्यातमा जम्मा तथ्याङ्क मात्र हुन्छ।",
    summary: "यस हप्ता",
    inquiries: "प्राप्त सोधपुछ",
    average: "औसत जवाफ समय",
    recovered: "फर्किएको बिक्री",
    lost: "हराएका",
    export: "हप्ताको सारांश निकाल्नुहोस्",
    formTitle: "सोधपुछ थप्नुहोस्",
    name: "ग्राहकको नाम",
    channel: "च्यानल",
    asked: "उहाँले के सोध्नुभयो?",
    add: "सोधपुछ थप्नुहोस्",
    noInquiries: "अहिलेसम्म सोधपुछ छैन",
    noInquiriesDetail: "सम्झनुपर्ने पहिलो सन्देश थप्नुहोस्। यो फोनबाट केही बाहिर जाँदैन।",
    received: "प्राप्त",
    waiting: "पर्खाइ",
    repliedIn: "जवाफ दिइयो",
    markReplied: "जवाफ दिइयो",
    markRecovered: "बिक्री भयो",
    markLost: "हरायो",
    amount: "बिक्री रकम (रु)",
    saveRecovered: "बिक्री रकम सुरक्षित गर्नुहोस्",
    cancel: "रद्द",
    clear: "सबै स्थानीय डाटा मेटाउनुहोस्",
    remove: "सोधपुछ हटाउनुहोस्",
    npr: "रु",
  },
} as const;

const CHANNEL_LABELS: Record<Language, Record<Channel, string>> = {
  en: { facebook: "Facebook", instagram: "Instagram", tiktok: "TikTok", whatsapp: "WhatsApp", other: "Other" },
  ne: { facebook: "फेसबुक", instagram: "इन्स्टाग्राम", tiktok: "टिकटक", whatsapp: "ह्वाट्सएप", other: "अन्य" },
};

function loadInquiries(): Inquiry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.map(normalizeInquiry).filter((item): item is Inquiry => item !== null)
      : [];
  } catch {
    return [];
  }
}

function formatTime(timestamp: number, language: Language): string {
  return new Date(timestamp).toLocaleTimeString(language === "ne" ? "ne-NP" : "en-NP", {
    hour: "numeric",
    minute: "2-digit",
  });
}

function InboxPrototype() {
  const [language, setLanguage] = useState<Language>("en");
  const [items, setItems] = useState<Inquiry[]>([]);
  const [name, setName] = useState("");
  const [channel, setChannel] = useState<Channel>("facebook");
  const [want, setWant] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [recoveringId, setRecoveringId] = useState<string | null>(null);
  const [recoveryAmount, setRecoveryAmount] = useState("");
  const t = COPY[language];

  useEffect(() => {
    setItems(loadInquiries());
    setHydrated(true);
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {
      // Browser storage can be unavailable; keep the active session usable.
    }
  }, [items, hydrated]);

  const addInquiry = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim() || !want.trim()) return;
    const timeIn = Date.now();
    setItems((current) => [{
      id: `${timeIn}-${Math.random().toString(36).slice(2, 7)}`,
      timeIn,
      customer: name.trim(),
      channel,
      want: want.trim(),
      replyAt: null,
      outcome: "open",
      orderValue: null,
    }, ...current]);
    setName("");
    setWant("");
  };

  const updateInquiry = (id: string, update: (item: Inquiry) => Inquiry) =>
    setItems((current) => current.map((item) => item.id === id ? update(item) : item));

  const markReplied = (id: string) => updateInquiry(id, (item) => ({ ...item, replyAt: item.replyAt ?? Date.now() }));
  const markLost = (id: string) => updateInquiry(id, (item) => ({
    ...item,
    replyAt: item.replyAt ?? Date.now(),
    outcome: "lost",
    orderValue: null,
  }));
  const saveRecovered = (id: string) => {
    if (!recoveryAmount.trim() || parseOrderValue(recoveryAmount) <= 0) return;
    updateInquiry(id, (item) => ({
      ...item,
      replyAt: item.replyAt ?? Date.now(),
      outcome: "recovered",
      orderValue: parseOrderValue(recoveryAmount),
    }));
    setRecoveringId(null);
    setRecoveryAmount("");
  };

  const summary = summarizeWeek(items, now);
  const exportSummary = () => {
    const blob = new Blob([weekSummaryText(summary, language, now)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "hami-week-summary.txt";
    anchor.click();
    URL.revokeObjectURL(url);
  };
  const clearAll = () => {
    if (window.confirm(language === "ne" ? "सबै स्थानीय डाटा मेटाउने?" : "Clear all local data?")) setItems([]);
  };

  return (
    <main className={language === "ne" ? "font-nepali" : undefined}>
      <PageHeader eyebrow={t.eyebrow} title={t.title} lede={t.lede} containerClassName="max-w-3xl" />
      <Container className="max-w-3xl py-6 sm:py-10">
        <div className="mb-5 flex items-center justify-between gap-3">
          <p className="text-xs text-muted">{t.privacy}</p>
          <button
            type="button"
            onClick={() => setLanguage((current) => current === "en" ? "ne" : "en")}
            className="shrink-0 rounded-lg border border-line px-3 py-2 text-sm font-semibold text-ink"
          >
            {language === "en" ? "नेपाली" : "English"}
          </button>
        </div>

        <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm leading-6 text-muted">
          <FlaskConical className="mt-0.5 size-5 shrink-0 text-amber-300" aria-hidden="true" />
          <p>{language === "ne" ? "नमुना मात्र। ग्राहकको सन्देश वा सम्पर्क विवरण बाहिर पठाइँदैन।" : "Prototype only. Customer messages and contact details are never sent anywhere."}</p>
        </div>

        <section aria-label={t.summary} className="mb-6">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-display text-xl text-ink">{t.summary}</h2>
            <Button type="button" size="sm" onClick={exportSummary}>
              <Download className="size-4" aria-hidden="true" /> {t.export}
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              { label: t.inquiries, value: String(summary.inquiries) },
              { label: t.average, value: summary.averageReplyMs === null ? "—" : formatDuration(summary.averageReplyMs, language) },
              { label: t.recovered, value: `${t.npr} ${summary.recoveredSalesNpr.toLocaleString("en-NP")}` },
              { label: t.lost, value: String(summary.lost) },
            ].map((stat) => (
              <div key={stat.label} className="min-w-0 rounded-xl border border-line bg-surface p-3">
                <p className="text-xs font-medium leading-4 text-muted">{stat.label}</p>
                <p className="mt-1 break-words font-display text-xl text-ink">{stat.value}</p>
              </div>
            ))}
          </div>
        </section>

        <section aria-label={t.formTitle} className="mb-6 rounded-xl border border-line bg-surface p-4">
          <h2 className="font-display text-xl text-ink">{t.formTitle}</h2>
          <form className="mt-3 grid gap-3" onSubmit={addInquiry}>
            <input value={name} onChange={(event) => setName(event.target.value)} required autoComplete="off" placeholder={t.name} aria-label={t.name} className="min-h-11 rounded-lg border border-line bg-background px-3 text-base text-ink placeholder:text-muted/60" />
            <select value={channel} onChange={(event) => setChannel(event.target.value as Channel)} aria-label={t.channel} className="min-h-11 rounded-lg border border-line bg-background px-3 text-base text-ink">
              {(Object.keys(CHANNEL_LABELS[language]) as Channel[]).map((value) => <option key={value} value={value}>{CHANNEL_LABELS[language][value]}</option>)}
            </select>
            <input value={want} onChange={(event) => setWant(event.target.value)} required autoComplete="off" placeholder={t.asked} aria-label={t.asked} className="min-h-11 rounded-lg border border-line bg-background px-3 text-base text-ink placeholder:text-muted/60" />
            <Button type="submit" className="min-h-11 w-full sm:w-auto sm:justify-self-end"><Plus className="size-4" aria-hidden="true" /> {t.add}</Button>
          </form>
        </section>

        <section aria-label={t.inquiries} className="grid gap-3">
          {items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-line p-7 text-center">
              <p className="font-semibold text-ink">{t.noInquiries}</p>
              <p className="mt-1 text-sm text-muted">{t.noInquiriesDetail}</p>
            </div>
          ) : items.map((item) => {
            const elapsed = Math.max(0, (item.replyAt ?? now) - item.timeIn);
            const isRecovering = recoveringId === item.id;
            return (
              <article key={item.id} className="rounded-xl border border-line bg-surface p-4">
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <h3 className="break-words font-semibold text-ink">{item.customer}</h3>
                      <span className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">{CHANNEL_LABELS[language][item.channel]}</span>
                    </div>
                    <p className="mt-1 break-words text-sm text-muted">{item.want}</p>
                  </div>
                  <button type="button" onClick={() => setItems((current) => current.filter((entry) => entry.id !== item.id))} aria-label={t.remove} className="rounded p-2 text-muted hover:text-ink"><Trash2 className="size-4" aria-hidden="true" /></button>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
                  <span>{t.received} {formatTime(item.timeIn, language)}</span>
                  <span className="inline-flex items-center gap-1 font-semibold text-accent"><Timer className="size-3" aria-hidden="true" />{item.replyAt === null ? `${t.waiting} ${formatDuration(elapsed, language)}` : `${t.repliedIn} ${formatDuration(elapsed, language)}`}</span>
                  {item.outcome === "recovered" && <span className="font-semibold text-emerald-300">{t.recovered}: {t.npr} {(item.orderValue ?? 0).toLocaleString("en-NP")}</span>}
                  {item.outcome === "lost" && <span className="font-semibold text-red-300">{t.lost}</span>}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="secondary" onClick={() => markReplied(item.id)} disabled={item.replyAt !== null}>{t.markReplied}</Button>
                  <Button type="button" size="sm" variant="secondary" onClick={() => { setRecoveringId(item.id); setRecoveryAmount(item.orderValue?.toString() ?? ""); }}>{t.markRecovered}</Button>
                  <Button type="button" size="sm" variant="secondary" onClick={() => markLost(item.id)}>{t.markLost}</Button>
                </div>
                {isRecovering && (
                  <div className="mt-3 grid gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 sm:grid-cols-[1fr_auto_auto]">
                    <input type="number" inputMode="decimal" min="1" step="0.01" required value={recoveryAmount} onChange={(event) => setRecoveryAmount(event.target.value)} placeholder={t.amount} aria-label={t.amount} className="min-h-10 rounded-lg border border-line bg-background px-3 text-base text-ink placeholder:text-muted/60" />
                    <Button type="button" size="sm" onClick={() => saveRecovered(item.id)} disabled={!recoveryAmount.trim() || parseOrderValue(recoveryAmount) <= 0}>{t.saveRecovered}</Button>
                    <Button type="button" size="sm" variant="secondary" onClick={() => setRecoveringId(null)}>{t.cancel}</Button>
                  </div>
                )}
              </article>
            );
          })}
        </section>

        {items.length > 0 && <div className="mt-6 text-right"><button type="button" onClick={clearAll} className="text-sm text-muted underline-offset-4 hover:underline">{t.clear}</button></div>}
      </Container>
    </main>
  );
}
