import { type FormEvent, type ReactNode, useMemo, useState } from "react";
import { ArrowUpRight, Check } from "lucide-react";
import { z } from "zod";
import { SITE, projectTypes, timelines } from "@/lib/content";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { TextLink } from "@/components/layout/text-link";

const schema = z.object({
  name: z.string().trim().min(2, "Name is required.").max(120),
  company: z.string().trim().max(160).optional(),
  email: z.string().trim().email("A valid email is required."),
  phone: z.string().trim().max(40).optional(),
  projectType: z
    .string()
    .refine(
      (value): value is (typeof projectTypes)[number] =>
        (projectTypes as readonly string[]).includes(value),
      "Choose what you are exploring.",
    ),
  problem: z.string().trim().min(12, "Give us a little more context.").max(4000),
  timeline: z.string().trim().max(40).optional(),
  details: z.string().trim().max(2000).optional(),
  consent: z.boolean().refine((value) => value, "Consent is required to send this inquiry."),
});

type FieldErrors = Partial<Record<keyof z.infer<typeof schema>, string>>;

const selectClass =
  "h-11 w-full rounded-md border border-line bg-void px-3 text-sm text-fg outline-none transition-[border-color,box-shadow] duration-150 focus-visible:border-cyan focus-visible:shadow-[var(--shadow-glow)]";

function buildMailto(values: z.infer<typeof schema>) {
  const lines = [
    `Name: ${values.name}`,
    `Email: ${values.email}`,
    values.company ? `Company: ${values.company}` : null,
    values.phone ? `Phone: ${values.phone}` : null,
    `Exploring: ${values.projectType}`,
    values.timeline ? `Timeline: ${values.timeline}` : null,
    "",
    "Context:",
    values.problem,
    values.details ? `\nNotes:\n${values.details}` : null,
  ].filter((line) => line !== null);
  const subject = encodeURIComponent(`Forge inquiry — ${values.projectType}`);
  const body = encodeURIComponent(lines.join("\n"));
  return `mailto:${SITE.email}?subject=${subject}&body=${body}`;
}

export function ProjectForm() {
  const [submitted, setSubmitted] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [mailto, setMailto] = useState<string | null>(null);
  const checks = useMemo(
    () => ["A human review of every request", "Clear scope before any build", "No unsupported promises"],
    [],
  );

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    if (String(data.hp_field || "").trim()) {
      setSubmitted(true);
      return;
    }
    const parsed = schema.safeParse({
      name: data.name,
      company: data.company || undefined,
      email: data.email,
      phone: data.phone || undefined,
      projectType: data.projectType,
      problem: data.problem,
      timeline: data.timeline || undefined,
      details: data.details || undefined,
      consent: data.consent === "on",
    });
    if (!parsed.success) {
      const next: FieldErrors = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0];
        if (typeof key === "string" && !next[key as keyof FieldErrors]) {
          next[key as keyof FieldErrors] = issue.message;
        }
      }
      setErrors(next);
      return;
    }
    setErrors({});
    const href = buildMailto(parsed.data);
    setMailto(href);
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="flex min-h-96 flex-col justify-center rounded-xl border border-line bg-surface p-8">
        <div className="mb-6 grid size-10 place-items-center rounded-full bg-fg text-void">
          <Check className="size-5" />
        </div>
        <p className="font-mono text-kicker uppercase tracking-[0.16em] text-cyan">
          Request prepared
        </p>
        <h3 className="mt-3 font-display text-3xl font-semibold tracking-tight text-fg">
          That’s a useful first step.
        </h3>
        <p className="mt-3 max-w-md text-sm leading-relaxed text-muted">
          Nothing is stored on our servers from this page. Open your email client
          to send the inquiry directly to {SITE.email}.
        </p>
        {mailto ? (
          <Button asChild className="mt-6 w-fit">
            <a href={mailto}>
              Open email client
              <ArrowUpRight />
            </a>
          </Button>
        ) : null}
        <div className="mt-6">
          <TextLink to="/">Back to home</TextLink>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-line bg-surface p-5 sm:p-8">
      <form className="grid gap-5" onSubmit={onSubmit} noValidate>
        <div className="sr-only" aria-hidden="true">
          <label htmlFor="hp_field">Leave this field empty</label>
          <input id="hp_field" name="hp_field" tabIndex={-1} autoComplete="off" />
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="name" label="Name" required error={errors.name}>
            <Input id="name" name="name" placeholder="Your name" autoComplete="name" />
          </Field>
          <Field id="company" label="Company or venture">
            <Input id="company" name="company" placeholder="Company, venture, or team" />
          </Field>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="email" label="Email" required error={errors.email}>
            <Input id="email" name="email" type="email" placeholder="you@company.com" autoComplete="email" />
          </Field>
          <Field id="phone" label="Phone">
            <Input id="phone" name="phone" placeholder="Optional" autoComplete="tel" />
          </Field>
        </div>
        <Field id="projectType" label="What are you exploring?" required error={errors.projectType}>
          <select id="projectType" name="projectType" defaultValue="" className={selectClass} required>
            <option value="" disabled>
              Select one
            </option>
            {projectTypes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </Field>
        <Field id="problem" label="What should we understand first?" required error={errors.problem}>
          <Textarea
            id="problem"
            name="problem"
            placeholder="Describe the business need, opportunity, or question."
          />
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="timeline" label="Timeline">
            <select id="timeline" name="timeline" defaultValue="" className={selectClass}>
              <option value="">Choose a range</option>
              {timelines.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field id="details" label="Anything else?">
            <Input id="details" name="details" placeholder="Links, constraints, context" />
          </Field>
        </div>
        <label className="flex items-start gap-3 text-sm leading-relaxed text-muted">
          <input
            id="consent"
            name="consent"
            type="checkbox"
            className="mt-1 size-4 shrink-0 accent-cyan"
          />
          <span>
            I agree to Forge using this information to respond to my
            conversation request.
          </span>
        </label>
        {errors.consent ? <p className="text-xs text-amber">{errors.consent}</p> : null}
        <Button type="submit" className="w-full sm:w-auto">
          Start the conversation
          <ArrowUpRight />
        </Button>
        <p className="font-mono text-micro text-dim">
          Your details are used only to compose this inquiry. No automatic outreach
          is triggered, and nothing is stored on our servers from this page.
        </p>
      </form>
      <ul className="mt-8 hidden gap-3 text-sm text-muted lg:grid">
        {checks.map((item) => (
          <li key={item} className="flex items-center gap-2">
            <Check className="size-4 text-cyan" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Field({
  id,
  label,
  required,
  error,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <Label htmlFor={id}>
        {label}
        {required ? <span className="text-cyan"> *</span> : null}
      </Label>
      {children}
      {error ? <p className="mt-1.5 text-xs text-amber">{error}</p> : null}
    </div>
  );
}
