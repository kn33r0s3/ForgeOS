import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";

export const Route = createFileRoute("/build-log")({
  component: BuildLogPage,
  head: () => ({
    meta: [
      { title: "Build log — Hami" },
      {
        name: "description",
        content:
          "The sequence of real builds and progress, in order. Every entry is a measured result or an explicit zero. Nothing is invented.",
      },
    ],
  }),
});

/**
 * A build-log status. States are told by type and border, not by new
 * hues: verified uses wheat, staged and subgate use amber, contradicted
 * uses the existing danger red and is always shown.
 */
type BuildLogStatus = "verified" | "staged" | "subgate" | "contradicted";

type BuildLogEntry = {
  date: string;
  title: string;
  evidence: string;
  statuses: [BuildLogStatus, ...BuildLogStatus[]];
  statusNote?: string;
};

/**
 * The verified build sequence, newest first. Every entry is a measured
 * result or an explicit zero. Nothing here is invented, added, or
 * altered — the list is the record.
 */
const ENTRIES: BuildLogEntry[] = [
  {
    date: "18 Nov 2026",
    title: "Visual map live (Hami Systems)",
    evidence:
      "The one-Hami map (8 gates, every subgate) is live on the Knee Rose portfolio and staged on the Hami site. Verified live by a browser check (central node, 8 gates, Gate 1 expands).",
    statuses: ["verified"],
  },
  {
    date: "18 Nov 2026",
    title: "Proof ledger page built",
    evidence:
      "src/routes/ledger.tsx (6,658 B, 185 lines). Typecheck passed, Vite build passed, the /ledger route is registered. All 6 real claims render with state + evidence.",
    statuses: ["verified", "staged"],
  },
  {
    date: "18 Nov 2026",
    title: "Hami chat subgate passed",
    evidence:
      "The Hami chat path is staged (Vercel → tunnel → guarded gateway → local Hami server). A borrowed-model reply is not Hami verification and is not accepted.",
    statuses: ["verified"],
  },
  {
    date: "18 Nov 2026",
    title: "Hami Systems live on Knee Rose",
    evidence:
      "The gated pop-up (one script tag) is live; the button opens, the panel prints its gate line. The widget now waits 90 s.",
    statuses: ["verified"],
  },
  {
    date: "18 Nov 2026",
    title: "Knee Rose interactive terminal live",
    evidence:
      "A real terminal (help, whoami, projects, music, play, hami, about, contact, clear, exit) + music player with 3 tracks (Summit, Kanai Huncha Mast, Pilkington Dr 37). Cursor fixed (green blink right after \"$\").",
    statuses: ["verified"],
  },
  {
    date: "18 Nov 2026",
    title: "Gates 007 + 008 done and verified",
    evidence:
      "007: 1,380 backend tests passed, gates tests 14/14, GREEN. 008: 64 tests passed, gates 14/14, GREEN. Telegram delivery is a subgate (owner channel not configured).",
    statuses: ["verified"],
  },
  {
    date: "18 Nov 2026",
    title: "M7-H parked",
    evidence:
      "p95 passes all 3,000 viewers (median 11.2 ms); p99 fails, only 115 of 3,000 pass (median ~294 ms). The 9-streamer / 4,000-viewer target is NOT proven on one laptop.",
    statuses: ["contradicted"],
    statusNote: "target not met",
  },
  {
    date: "17 Nov 2026",
    title: "M6-H passed",
    evidence:
      "1,000 publishers, 2,000 viewers, p95 0.34 ms, p99 17.8 ms, zero NACKs. The fix was disabling mDNS.",
    statuses: ["verified"],
  },
  {
    date: "18 Nov 2026",
    title: "Attempt 13 stalled — three identical stalls, one finished verdict",
    evidence:
      "All 3,000 publishers show frames=0 since 19:10:59. Three re-runs stall identically (profile, tuned, tuned2), same ~1-minute signature. The tuned run finished 19:34:07: 60/3,000 tracks complete, all 6,000 connections died. The GC heap fix did NOT prevent the stall — a different single common cause.",
    statuses: ["subgate"],
    statusNote: "in progress — not a dead end",
  },
  {
    date: "18 Nov 2026",
    title: "SFT held-out eval: adapter loses",
    evidence:
      "Base 73/120 vs adapter 58/120 (20 rows). Data quality is the blocker.",
    statuses: ["verified"],
  },
];

/**
 * Border + text classes for a build-log status. The first status of an
 * entry is its primary one and sets the card's left border.
 */
function statusClasses(status: BuildLogStatus): { tag: string; bar: string } {
  if (status === "contradicted") {
    return {
      tag: "border-ledger-danger text-ledger-danger",
      bar: "border-l-ledger-danger",
    };
  }
  if (status === "verified") {
    return {
      tag: "border-ledger-wheat text-ledger-wheat",
      bar: "border-l-ledger-wheat",
    };
  }
  return {
    tag: "border-ledger-amber text-ledger-amber",
    bar: "border-l-ledger-amber",
  };
}

/** Border + text classes for a status note box, in the entry's own colour. */
function noteClasses(status: BuildLogStatus): string {
  if (status === "contradicted") {
    return "border-ledger-danger bg-ledger-black text-ledger-danger";
  }
  return "border-ledger-amber bg-ledger-black text-ledger-amber";
}

/**
 * The latest build, in a .term-window, matching the home LiveStrip and
 * the ledger page's LatestChange terminal. The entry renders only with
 * its date, evidence, and status (the ledger gate).
 */
function LatestEntry() {
  const latest = ENTRIES[0];
  return (
    <div className="term-window">
      <div className="term-titlebar">
        <span className="term-dot term-dot--red" aria-hidden="true" />
        <span className="term-dot term-dot--yellow" aria-hidden="true" />
        <span className="term-dot term-dot--green" aria-hidden="true" />
        <span>niroj@hami: ~</span>
      </div>
      <div className="term-body">
        <p className="term-prompt">hami build-log --latest</p>
        {latest ? (
          <>
            <p>
              [{latest.statuses.join(" + ")}] {latest.title}
            </p>
            <p className="text-ink">{latest.evidence}</p>
            <p className="text-muted">{latest.date}</p>
          </>
        ) : (
          <p className="text-muted">no build yet</p>
        )}
        <p>
          <span className="term-prompt">hami build-log</span>{" "}
          <span className="term-cursor" aria-hidden="true" />
        </p>
      </div>
    </div>
  );
}

/**
 * One build entry, in sequence. The number is the entry's place in the
 * newest-first order. A contradicted or subgate entry is shown, never
 * hidden, and carries its status note in its own colour.
 */
function EntryCard({ entry, index }: { entry: BuildLogEntry; index: number }) {
  const primary = statusClasses(entry.statuses[0]);
  return (
    <article
      className={`rounded-md border border-ledger-border border-l-4 ${primary.bar} bg-ledger-surface p-5 shadow-md sm:p-6`}
      aria-label={`${entry.date}: ${entry.title}`}
    >
      <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
        <span className="font-bold text-ledger-ink">
          {String(index + 1).padStart(2, "0")}
        </span>
        <span className="text-ledger-muted">{entry.date}</span>
        {entry.statuses.map((status) => {
          const classes = statusClasses(status);
          return (
            <span
              key={status}
              className={`rounded-sm border px-2 py-0.5 font-bold uppercase tracking-wider ${classes.tag}`}
            >
              {status}
            </span>
          );
        })}
      </div>
      <h2 className="mt-4 font-display text-lg font-bold leading-snug text-ledger-ink">
        {entry.title}
      </h2>
      <p className="mt-3 text-base leading-7 text-ledger-ink">
        {entry.evidence}
      </p>
      {entry.statusNote ? (
        <p
          className={`mt-3 border px-3 py-2 text-sm leading-6 ${noteClasses(entry.statuses[0])}`}
        >
          {entry.statusNote}
        </p>
      ) : null}
    </article>
  );
}

function BuildLogPage() {
  return (
    <>
      <section className="border-b border-line bg-background" aria-label="Latest build">
        <Container className="py-8 sm:py-10">
          <p className="font-ledger-wordmark text-5xl leading-none text-ledger-amber sm:text-6xl">
            Hami
          </p>
          <h1 className="mt-3 font-ledger-heading text-2xl leading-snug text-ledger-ink sm:text-3xl">
            निर्माण लग
          </h1>
          <p className="mt-1 font-display text-xl font-bold text-ledger-ink">
            Build log
          </p>
          <p className="mt-3 max-w-2xl text-base leading-7 text-ledger-muted">
            Builds and progress, newest first. Each entry carries its date,
            its evidence, and its status. Subgates and contradicted entries
            are shown, never hidden.
          </p>
          <div className="mt-6">
            <LatestEntry />
          </div>
        </Container>
      </section>
      <section className="bg-background" aria-label="Build entries">
        <Container className="py-8 sm:py-10">
          <div className="grid gap-5">
            {ENTRIES.map((entry, index) => (
              <EntryCard
                key={`${entry.date}-${entry.title}`}
                entry={entry}
                index={index}
              />
            ))}
          </div>
          <p className="mt-8 border-t border-ledger-border pt-5 font-mono text-sm leading-6 text-ledger-muted">
            Every entry on this log is a measured result or an explicit zero.
            Nothing is invented.
          </p>
        </Container>
      </section>
    </>
  );
}
