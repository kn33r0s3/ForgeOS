import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";

/**
 * HamiAgent — Hami as a permanent agent, available on every page.
 *
 * Mounted once in __root.tsx, so it lives above route changes: the
 * conversation survives navigation, and it survives a reload too (the
 * thread is kept in localStorage). This is an agent, not a temporary
 * chatbot — it is always here, it remembers, and it says plainly when
 * it does not know.
 *
 * It talks to the same /api/hami/chat route as the /meet-hami page.
 * It cannot contact anyone, spend money, or change records; it only talks.
 */

type ChatMsg = { role: "user" | "assistant"; content: string };

const STORAGE_KEY = "hami-agent-thread-v1";

const FIRST_MESSAGE: ChatMsg = {
  role: "assistant",
  content:
    "Namaste — I am Hami. I am a living system for understanding and acting on Nepal's economy. Ask me what I know, what is still unknown, or what to investigate next. I answer from evidence, and I say plainly when I do not know.",
};

const SUGGESTIONS = [
  "What is Hami?",
  "What is still unknown?",
  "नेपालीमा भन्नुहोस् — हामी के हो?",
];

function loadThread(): ChatMsg[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [FIRST_MESSAGE];
    const parsed = JSON.parse(raw) as ChatMsg[];
    if (!Array.isArray(parsed) || parsed.length === 0) return [FIRST_MESSAGE];
    return parsed.filter(
      (m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string",
    );
  } catch {
    return [FIRST_MESSAGE];
  }
}

export function HamiAgent() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([FIRST_MESSAGE]);
  const [hydrated, setHydrated] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState<"checking" | "online" | "offline">("checking");
  const listRef = useRef<HTMLDivElement>(null);

  // Load the remembered thread once (client-only; localStorage is not
  // available during server rendering).
  useEffect(() => {
    setMessages(loadThread());
    setHydrated(true);
  }, []);

  // Remember the thread so the agent never forgets a conversation.
  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-30)));
    } catch {
      // Storage full or unavailable — the in-memory thread still works.
    }
  }, [messages, hydrated]);

  useEffect(() => {
    if (open) {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
    }
  }, [messages, busy, open]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setError(null);
    setInput("");
    const nextMessages: ChatMsg[] = [...messages, { role: "user", content: trimmed }];
    setMessages(nextMessages);
    setBusy(true);
    try {
      const history = nextMessages
        .filter((m) => m.role !== "assistant" || m !== FIRST_MESSAGE)
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content }));
      const response = await fetch("/api/hami/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, history }),
      });
      const data = (await response.json().catch(() => null)) as
        | { reply?: string; detail?: string }
        | null;
      if (!response.ok) {
        throw new Error(data?.detail ?? `Hami answered with HTTP ${response.status}.`);
      }
      if (!data?.reply) throw new Error("Hami returned an empty reply.");
      setMessages([...nextMessages, { role: "assistant", content: data.reply }]);
      setConnected("online");
    } catch (err) {
      setConnected("offline");
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach Hami AI. The Mac tunnel may be down — try again in a moment.",
      );
    } finally {
      setBusy(false);
    }
  }

  function clearThread() {
    setMessages([FIRST_MESSAGE]);
    setError(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignore storage errors.
    }
  }

  const statusDot =
    connected === "online"
      ? "bg-success"
      : connected === "offline"
        ? "bg-danger"
        : "bg-warning";
  const statusLabel =
    connected === "online"
      ? "Hami AI is online"
      : connected === "offline"
        ? "Hami AI is unreachable right now"
        : "Checking Hami AI…";

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3" aria-label="Hami agent">
      {open ? (
        <section
          className="flex h-[min(70vh,560px)] w-[min(92vw,380px)] flex-col overflow-hidden rounded-xl border-2 border-line bg-surface shadow-md"
          aria-label="Talk with Hami"
        >
          <header className="flex items-center gap-3 border-b border-line bg-card px-4 py-3">
            <div className="grid size-10 shrink-0 place-items-center border border-ink bg-ink font-display text-lg font-black text-paper" aria-hidden="true">
              H
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-display text-base font-extrabold leading-tight text-fg">Hami</p>
              <p className="flex items-center gap-1.5 text-xs text-muted">
                <span className={`size-2 rounded-full ${statusDot}`} aria-hidden="true" />
                {statusLabel}
              </p>
            </div>
            <Link
              to="/meet-hami"
              className="shrink-0 rounded-full border border-line px-2.5 py-1.5 text-xs font-semibold text-muted transition-colors hover:text-fg"
            >
              Full chat
            </Link>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close Hami"
              className="grid size-8 shrink-0 place-items-center rounded-full border border-line text-lg leading-none text-muted transition-colors hover:text-fg"
            >
              ×
            </button>
          </header>

          <div ref={listRef} className="flex-1 overflow-y-auto p-4" aria-live="polite">
            <div className="grid gap-3">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={
                    msg.role === "user"
                      ? "ml-auto max-w-[85%] rounded-xl rounded-br-sm bg-accent px-3.5 py-2.5 text-sm leading-6 text-black"
                      : "mr-auto max-w-[85%] rounded-xl rounded-bl-sm border border-line bg-card px-3.5 py-2.5 text-sm leading-6 text-fg"
                  }
                >
                  {msg.role === "assistant" && (
                    <p className="mb-0.5 text-[11px] font-bold uppercase tracking-[0.14em] text-accent">
                      Hami
                    </p>
                  )}
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              ))}
              {busy && (
                <div className="mr-auto max-w-[85%] rounded-xl rounded-bl-sm border border-line bg-card px-3.5 py-2.5 text-sm text-muted">
                  Hami is thinking…
                </div>
              )}
            </div>
          </div>

          {error && (
            <p role="alert" className="mx-4 mb-2 rounded-xl border border-danger bg-surface px-3 py-2 text-xs leading-5 text-fg">
              {error}
            </p>
          )}

          <div className="flex flex-wrap gap-1.5 px-4 pb-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => void send(s)}
                disabled={busy}
                className="rounded-full border border-line px-2.5 py-1.5 text-[11px] font-semibold text-muted transition-colors hover:text-fg disabled:opacity-60"
              >
                {s}
              </button>
            ))}
          </div>

          <form
            className="flex gap-2 border-t border-line bg-card p-3"
            onSubmit={(event) => {
              event.preventDefault();
              void send(input);
            }}
          >
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask Hami anything…"
              aria-label="Message Hami"
              className="min-h-11 min-w-0 flex-1 rounded-card border-2 border-line bg-black px-3 text-sm text-ink"
              disabled={busy}
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="min-h-11 shrink-0 rounded-card border-2 border-accent bg-accent px-4 text-sm font-extrabold text-black disabled:opacity-60"
            >
              {busy ? "…" : "Send"}
            </button>
          </form>

          <div className="flex items-center justify-between border-t border-line px-4 py-2">
            <p className="text-[11px] text-muted">Hami remembers this thread.</p>
            <button
              type="button"
              onClick={clearThread}
              disabled={busy}
              className="text-[11px] font-semibold text-muted underline-offset-2 hover:text-fg hover:underline disabled:opacity-60"
            >
              Start fresh
            </button>
          </div>
        </section>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close Hami" : "Talk with Hami"}
        aria-expanded={open}
        className="group relative grid size-14 place-items-center rounded-full border-2 border-accent bg-ink font-display text-2xl font-black text-paper shadow-md transition-transform hover:scale-105"
      >
        H
        <span
          className={`absolute -right-0.5 -top-0.5 size-3.5 rounded-full border-2 border-paper ${statusDot}`}
          aria-hidden="true"
        />
        <span className="pointer-events-none absolute right-full mr-3 hidden whitespace-nowrap rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-bold text-fg shadow-md group-hover:block">
          Talk with Hami
        </span>
      </button>
    </div>
  );
}
