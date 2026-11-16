import { useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export const Route = createFileRoute("/meet-hami")({
  component: MeetHamiPage,
  head: () => ({ meta: [{ title: "Meet Hami — Hami" }] }),
});

type ChatMsg = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "What is Hami?",
  "What does Hami know about Nepal's economy?",
  "What is still unknown?",
  "नेपालीमा भन्नुहोस् — हामी के हो?",
];

const FIRST_MESSAGE: ChatMsg = {
  role: "assistant",
  content:
    "Namaste — I am Hami. I am a living system for understanding and acting on Nepal's economy. Ask me what I know, what is still unknown, or what to investigate next. I answer from evidence, and I say plainly when I do not know.",
};

function MeetHamiPage() {
  const [messages, setMessages] = useState<ChatMsg[]>([FIRST_MESSAGE]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState<"checking" | "online" | "offline">("checking");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, busy]);

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

  return (
    <main className="relative isolate overflow-hidden py-16 sm:py-20 lg:py-24">
      <div className="hero-glow -z-10" aria-hidden="true" />
      <Container className="max-w-3xl">
        <Eyebrow>Meet Hami</Eyebrow>
        <h1 className="font-display font-black tracking-[-0.045em] text-display text-fg">
          Talk with <span className="text-muted">Hami.</span>
        </h1>
        <p className="mt-4 max-w-2xl text-lede text-muted">
          Hami is the system we are building together — it understands Nepal&apos;s
          economy from evidence, and it says plainly what it does not know yet.
          This chat runs on the owner&apos;s Mac, live.
        </p>
        <p className="mt-2 text-sm text-muted">
          {connected === "online" ? (
            <span className="inline-flex items-center gap-2">
              <span className="size-2 rounded-full bg-success" aria-hidden="true" />
              Hami AI is online
            </span>
          ) : connected === "offline" ? (
            <span className="inline-flex items-center gap-2">
              <span className="size-2 rounded-full bg-danger" aria-hidden="true" />
              Hami AI is unreachable right now
            </span>
          ) : (
            "Checking Hami AI…"
          )}
        </p>

        <div
          ref={listRef}
          className="mt-8 max-h-[55vh] overflow-y-auto rounded-xl border border-line bg-surface p-5"
          aria-live="polite"
        >
          <div className="grid gap-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={
                  msg.role === "user"
                    ? "ml-auto max-w-[85%] rounded-xl rounded-br-sm bg-accent px-4 py-3 text-sm leading-6 text-black"
                    : "mr-auto max-w-[85%] rounded-xl rounded-bl-sm border border-line bg-card px-4 py-3 text-sm leading-6 text-fg"
                }
              >
                {msg.role === "assistant" && (
                  <p className="mb-1 text-xs font-bold uppercase tracking-[0.14em] text-accent">
                    Hami
                  </p>
                )}
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}
            {busy && (
              <div className="mr-auto max-w-[85%] rounded-xl rounded-bl-sm border border-line bg-card px-4 py-3 text-sm text-muted">
                Hami is thinking…
              </div>
            )}
          </div>
        </div>

        {error && (
          <p role="alert" className="mt-4 rounded-xl border border-danger bg-surface px-4 py-3 text-sm text-fg">
            {error}
          </p>
        )}

        <form
          className="mt-4 flex gap-3"
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
            className="min-h-12 min-w-0 flex-1 rounded-card border-2 border-line bg-black px-4 text-base text-ink"
            disabled={busy}
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="min-h-12 rounded-card border-2 border-accent bg-accent px-5 font-extrabold text-black disabled:opacity-60"
          >
            {busy ? "…" : "Send"}
          </button>
        </form>

        <div className="mt-5 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => void send(s)}
              disabled={busy}
              className="rounded-full border border-line px-3 py-2 text-xs font-semibold text-muted transition-colors hover:text-fg disabled:opacity-60"
            >
              {s}
            </button>
          ))}
        </div>

        <p className="mt-8 text-xs leading-5 text-muted">
          Checkpoint build: Hami answers from its doctrine and the owner&apos;s
          Mac model (gpt-oss:20b). It does not yet read Hami&apos;s evidence
          database — that comes next. It cannot contact anyone, spend money,
          or change records; it only talks here.
        </p>
      </Container>
    </main>
  );
}
