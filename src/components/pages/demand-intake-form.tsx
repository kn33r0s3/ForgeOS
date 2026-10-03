import { type FormEvent, useState } from "react";
import { submitPublicDemandRequest } from "@/lib/content";

export function DemandIntakeForm() {
  const [content, setContent] = useState("");
  const [attempt, setAttempt] = useState<{ content: string; key: string } | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setIsSubmitting(true);

    const submittedContent = content.trim();
    const key = attempt?.content === submittedContent ? attempt.key : crypto.randomUUID();
    setAttempt({ content: submittedContent, key });
    const result = await submitPublicDemandRequest(submittedContent, key);

    setIsSubmitting(false);
    if (!result) {
      setMessage("The request was not confirmed. You can retry safely.");
      return;
    }
    if ("notOpen" in result) {
      setMessage("Online inquiries are not open yet. Your note was not submitted.");
      return;
    }

    setContent("");
    setAttempt(null);
    setMessage(
      `Request recorded as possible demand (record #${result.id}). It is not a qualified prospect, offer, or promise of follow-up.`,
    );
  }

  return (
    <section className="rounded-xl border border-line bg-surface p-5 sm:p-8">
      <p className="text-micro font-extrabold uppercase tracking-[0.12em] text-cyan">Submit a need</p>
      <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-fg">
        What should Hami understand?
      </h2>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        Your note is stored as an observed request and interpreted for clarity. It does not create a customer or opportunity, trigger outreach, or authorize work. This form does not ask for contact details or promise a reply.
      </p>
      <form className="mt-6 grid gap-4" onSubmit={onSubmit}>
        <label htmlFor="demand-content" className="text-sm font-medium text-fg">
          Describe the need or problem
        </label>
        <textarea
          id="demand-content"
          value={content}
          onChange={(event) => {
            setContent(event.target.value);
            if (attempt && event.target.value.trim() !== attempt.content) {
              setAttempt(null);
            }
          }}
          required
          maxLength={5000}
          rows={6}
          placeholder="What is needed, by whom, where, and what constraints matter?"
          className="w-full rounded-md border border-line bg-void px-3 py-3 text-sm text-fg outline-none transition-[border-color,box-shadow] focus-visible:border-cyan focus-visible:shadow-[var(--shadow-glow)]"
        />
        <p className="text-xs text-muted">
          Do not include sensitive information. Email addresses and phone-number patterns are redacted before storage. Up to 5,000 characters.
        </p>
        <button
          type="submit"
          disabled={isSubmitting || !content.trim()}
          className="btn-wipe btn-primary min-h-11 w-fit rounded-card border-2 border-black/70 bg-accent px-5 text-sm font-extrabold text-black hover:text-accent focus-visible:text-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "Recording…" : "Submit for understanding"}
        </button>
      </form>
      {message ? <p className="mt-4 text-sm text-muted" role="status">{message}</p> : null}
    </section>
  );
}
