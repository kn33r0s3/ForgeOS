import { useState, type FormEvent } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowLeft, ArrowRight, ClipboardList, RotateCcw, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Container } from "@/components/layout/container";
import {
  EMPTY_QUALIFICATION_ANSWERS,
  hasDuplicateTestContact,
  normalizeEmail,
  normalizePhone,
  qualificationStage,
  validateTestContact,
  type DemoContact,
  type QualificationAnswers,
} from "@/lib/forge-bot/qualification";

export const Route = createFileRoute("/bot-qualification-demo")({
  component: ForgeBotDemoPage,
  head: () => ({
    meta: [
      { title: "Forge Bot TEST demo — Hami" },
      { name: "robots", content: "noindex,nofollow" },
    ],
  }),
});

type DemoSubmission = {
  ref: string;
  contact: DemoContact;
  answers: QualificationAnswers;
  stage: ReturnType<typeof qualificationStage>;
};

const QUESTIONS = [
  {
    key: "destination",
    label: "Which destination are you considering?",
    type: "text",
  },
  {
    key: "course",
    label: "Which course or field?",
    type: "text",
  },
  {
    key: "timeline",
    label: "When do you expect to start?",
    type: "text",
  },
] as const;

function ForgeBotDemoPage() {
  const [answers, setAnswers] = useState<QualificationAnswers>({
    ...EMPTY_QUALIFICATION_ANSWERS,
  });
  const [contact, setContact] = useState<DemoContact>({ email: "", phone: "" });
  const [step, setStep] = useState(0);
  const [submissions, setSubmissions] = useState<DemoSubmission[]>([]);
  const [error, setError] = useState("");
  const [showSummary, setShowSummary] = useState(false);

  if (import.meta.env.PROD) {
    return (
      <main>
        <Container className="py-16">
          <h1 className="text-title">This test demo is not available here.</h1>
        </Container>
      </main>
    );
  }

  const answersComplete = step < 3;
  const isBudgetStep = step === 3;
  const isContactStep = step === 4;
  const question = QUESTIONS[step];
  const stage = qualificationStage(answers);

  function setAnswer(field: keyof QualificationAnswers, value: string) {
    setAnswers((current) => ({ ...current, [field]: value }));
    setError("");
  }

  function continueQuestion() {
    if (question && !answers[question.key].trim()) {
      setError("Complete this field before continuing.");
      return;
    }
    if (isBudgetStep) {
      const nextStage = qualificationStage(answers);
      if (nextStage !== "READY_FOR_OWNER_REVIEW") {
        setError("Enter a non-negative budget range with maximum at least minimum.");
        return;
      }
    }
    setError("");
    setStep((current) => Math.min(current + 1, 4));
  }

  function submitTestIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const contactError = validateTestContact(contact);
    if (contactError) {
      setError(contactError);
      return;
    }
    if (hasDuplicateTestContact(submissions.map((item) => item.contact), contact)) {
      setError("Duplicate TEST contact in this browser session; no new demo row was added.");
      return;
    }
    if (stage !== "READY_FOR_OWNER_REVIEW") {
      setError("Complete the fixed question sequence first.");
      return;
    }

    setSubmissions((current) => [
      ...current,
      {
        ref: `TEST-${String(current.length + 1).padStart(3, "0")}`,
        contact: {
          email: normalizeEmail(contact.email),
          phone: normalizePhone(contact.phone),
        },
        answers,
        stage,
      },
    ]);
    setShowSummary(false);
    setError("");
    setStep(0);
    setAnswers({ ...EMPTY_QUALIFICATION_ANSWERS });
    setContact({ email: "", phone: "" });
  }

  function resetDemo() {
    setSubmissions([]);
    setShowSummary(false);
    setError("");
    setStep(0);
    setAnswers({ ...EMPTY_QUALIFICATION_ANSWERS });
    setContact({ email: "", phone: "" });
  }

  return (
    <main>
      <Container className="py-12 sm:py-16">
        <div className="max-w-3xl">
          <p className="font-mono text-xs font-bold uppercase tracking-[0.18em] text-accent">
            Local prototype · TEST only
          </p>
          <h1 className="mt-3 text-title">Forge Bot qualification demo</h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted">
            Exercises a fixed, deterministic question sequence. A complete
            response is only ready for owner review; no customer qualification,
            booking, follow-up, or payment is inferred.
          </p>
        </div>

        <section
          role="alert"
          className="mt-8 flex items-start gap-3 border-2 border-warning/50 bg-card p-4"
        >
          <ShieldAlert className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden="true" />
          <div className="text-sm leading-6">
            <p className="font-bold text-ink">Do not enter real contact or customer data.</p>
            <p className="text-muted">
              This demo accepts only reserved `example.test` email addresses or
              reserved 202-555-0100–0199 test numbers. Values stay in this page&apos;s
              memory and disappear on reload; nothing is sent to Hami&apos;s API.
            </p>
          </div>
        </section>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <IntegrationState title="Email intake" state="Not connected" />
          <IntegrationState title="Cal.com booking" state="Owner URL not configured" />
          <IntegrationState title="Daily summary" state="Preview only; never sent" />
        </div>

        <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
          <section className="min-w-0 border-2 border-line bg-card p-5 sm:p-7" aria-labelledby="intake-title">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.16em] text-muted">
                  Fixed sequence · step {isContactStep ? 5 : step + 1} of 5
                </p>
                <h2 id="intake-title" className="mt-2 text-xl font-extrabold">
                  {isContactStep ? "TEST contact key" : "Qualification"}
                </h2>
              </div>
              <span className="rounded-card border border-line px-3 py-1 font-mono text-xs text-accent">
                {stage}
              </span>
            </div>

            <form className="mt-6" onSubmit={submitTestIntake}>
              {question ? (
                <QuestionField
                  label={question.label}
                  value={answers[question.key]}
                  onChange={(value) => setAnswer(question.key, value)}
                />
              ) : isBudgetStep ? (
                <fieldset>
                  <legend className="mb-3 text-sm font-bold">What budget range is expected (NPR)?</legend>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="budget-min">Minimum</Label>
                      <Input
                        id="budget-min"
                        type="number"
                        min="0"
                        step="1"
                        required
                        value={answers.budgetMinimum}
                        onChange={(event) => setAnswer("budgetMinimum", event.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor="budget-max">Maximum</Label>
                      <Input
                        id="budget-max"
                        type="number"
                        min="0"
                        step="1"
                        required
                        value={answers.budgetMaximum}
                        onChange={(event) => setAnswer("budgetMaximum", event.target.value)}
                      />
                    </div>
                  </div>
                </fieldset>
              ) : (
                <div className="grid gap-4">
                  <div>
                    <Label htmlFor="test-email">Reserved TEST email</Label>
                    <Input
                      autoComplete="off"
                      id="test-email"
                      type="email"
                      placeholder="lead@example.test"
                      value={contact.email}
                      onChange={(event) => {
                        setContact((current) => ({ ...current, email: event.target.value }));
                        setError("");
                      }}
                    />
                  </div>
                  <div>
                    <Label htmlFor="test-phone">Reserved TEST phone (optional alternative)</Label>
                    <Input
                      autoComplete="off"
                      id="test-phone"
                      type="tel"
                      placeholder="+1 202-555-0100"
                      value={contact.phone}
                      onChange={(event) => {
                        setContact((current) => ({ ...current, phone: event.target.value }));
                        setError("");
                      }}
                    />
                  </div>
                  <p className="text-xs leading-5 text-muted">
                    Provide either or both test keys. Dedupe runs only against
                    this page session.
                  </p>
                </div>
              )}

              {error ? (
                <p className="mt-4 text-sm font-semibold text-danger" role="alert">
                  {error}
                </p>
              ) : null}

              <div className="mt-6 flex flex-wrap gap-3">
                {step > 0 ? (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setError("");
                      setStep((current) => Math.max(current - 1, 0));
                    }}
                  >
                    <ArrowLeft aria-hidden="true" />
                    Back
                  </Button>
                ) : null}
                {answersComplete || isBudgetStep ? (
                  <Button type="button" onClick={continueQuestion}>
                    Continue
                    <ArrowRight aria-hidden="true" />
                  </Button>
                ) : (
                  <Button type="submit">
                    Add TEST submission
                    <ArrowRight aria-hidden="true" />
                  </Button>
                )}
              </div>
            </form>
          </section>

          <aside className="min-w-0 border-2 border-line bg-paper p-5 sm:p-7" aria-labelledby="summary-title">
            <div className="flex items-center gap-2 text-accent">
              <ClipboardList className="size-5" aria-hidden="true" />
              <h2 id="summary-title" className="text-lg font-extrabold text-ink">
                Session summary
              </h2>
            </div>
            <p className="mt-3 text-sm leading-6 text-muted">
              {submissions.length} TEST row{submissions.length === 1 ? "" : "s"} held in memory.
              No row is written to the substrate or revenue ledger.
            </p>

            {submissions.length ? (
              <div className="mt-5 overflow-x-auto">
                <table className="w-full min-w-[28rem] text-left text-xs">
                  <thead className="border-b border-line text-muted">
                    <tr>
                      <th className="py-2 pr-2">Ref</th>
                      <th className="py-2 pr-2">Destination / course</th>
                      <th className="py-2">Stage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {submissions.map((item) => (
                      <tr key={item.ref} className="border-b border-line/70 align-top">
                        <td className="py-3 pr-2 font-mono text-accent">{item.ref}</td>
                        <td className="py-3 pr-2">
                          {item.answers.destination} / {item.answers.course}
                        </td>
                        <td className="py-3">{item.stage}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            <div className="mt-5 flex flex-wrap gap-3">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={submissions.length === 0}
                onClick={() => setShowSummary((current) => !current)}
              >
                Preview owner summary
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={resetDemo}>
                <RotateCcw aria-hidden="true" />
                Reset
              </Button>
            </div>

            {showSummary ? (
              <pre className="mt-4 max-h-52 overflow-auto whitespace-pre-wrap border border-line bg-card p-3 font-mono text-xs leading-5 text-muted">
                {`TEST owner summary — ${submissions.length} in-memory submission(s)\n` +
                  submissions.map((item) => `${item.ref}: ${item.stage}`).join("\n")}
                {"\nNot emailed. Not commercial evidence."}
              </pre>
            ) : null}
          </aside>
        </div>
      </Container>
    </main>
  );
}

function QuestionField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <Label htmlFor="qualification-answer">{label}</Label>
      <Input
        autoComplete="off"
        id="qualification-answer"
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function IntegrationState({ title, state }: { title: string; state: string }) {
  return (
    <div className="border border-line bg-card px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-muted">{title}</p>
      <p className="mt-1 text-sm font-semibold text-ink">{state}</p>
    </div>
  );
}
