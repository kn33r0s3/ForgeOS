import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";

export const Route = createFileRoute("/terms")({
  component: TermsPage,
  head: () => ({
    meta: [
      { title: "Terms of Service — Hami" },
      {
        name: "description",
        content: "The rules and terms for using Hami. Version 1.0.",
      },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
});

function TermsPage() {
  return (
    <main className="bg-night py-14 sm:py-20">
      <Container className="max-w-3xl">
        <p className="font-mono text-[0.7rem] font-bold uppercase tracking-[0.22em] text-accent">
          Terms of Service · Version 1.0
        </p>
        <h1 className="mt-3 font-gothic text-4xl leading-tight text-ink sm:text-5xl">
          Rules for using Hami
        </h1>
        <p className="mt-4 text-sm leading-7 text-muted">
          Last updated: October 4, 2026. These terms govern your use of Hami. By creating an
          account, you agree to these terms.
        </p>

        <div className="mt-10 space-y-10 border-t border-accent/20 pt-10">
          <section>
            <h2 className="font-display text-xl font-bold text-ink">1. What Hami is</h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              Hami is a living system that understands what people need and turns understanding
              into real value. It is built in Kathmandu and serves everywhere equally. Hami is
              pre-revenue and experimental. Features may change, break, or be removed without
              notice.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-ink">2. Who can use Hami</h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              You must be at least 18 years old to create an account. By signing up, you confirm
              that you meet this requirement. Hami may ask for your date of birth to verify
              eligibility.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-ink">3. Your account</h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              You are responsible for keeping your account credentials secure. Do not share your
              account with others. Hami may suspend or close accounts that violate these terms.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-ink">4. How Hami works</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-7 text-muted">
              <li>
                <strong className="text-ink">Observes:</strong> Hami sees what is happening in the
                real world.
              </li>
              <li>
                <strong className="text-ink">Keeps evidence and uncertainty:</strong> Hami
                separates what is known from what is not.
              </li>
              <li>
                <strong className="text-ink">Acts only when authorized:</strong> Hami takes no
                external action without your permission.
              </li>
              <li>
                <strong className="text-ink">Learns from outcomes:</strong> What actually happens
                changes what Hami knows and can do next.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-ink">5. Your data</h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              Hami collects only what it needs to function. See our{" "}
              <a href="/privacy" className="font-bold text-accent underline">
                Privacy Information
              </a>{" "}
              for details. Hami does not sell your personal information. You may request deletion
              of your account and associated data at any time.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-ink">6. Acceptable use</h2>
            <p className="mt-3 text-sm leading-7 text-muted">You agree not to:</p>
            <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-7 text-muted">
              <li>Use Hami for any illegal purpose or in violation of any law.</li>
              <li>Attempt to harm, disrupt, or gain unauthorized access to Hami's systems.</li>
              <li>Submit false information or impersonate another person.</li>
              <li>Use Hami to spam, harass, or harm others.</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-ink">7. No guarantees</h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              Hami is provided "as is" without warranties of any kind. Hami does not guarantee
              any specific outcome, result, or availability. As a pre-revenue experimental
              system, Hami may have errors, downtime, or incomplete features.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-ink">8. Changes to these terms</h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              Hami may update these terms. When the version changes, you will be asked to accept
              the new terms before continuing to use your account. The version you accepted is
              recorded with your account.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold text-ink">9. Contact</h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              For questions about these terms, contact Hami through the channels listed on the
              homepage.
            </p>
          </section>
        </div>

        <p className="mt-10 border-t border-accent/20 pt-6 text-xs leading-6 text-muted">
          By creating a Hami account, you acknowledge that you have read, understood, and agree
          to be bound by these Terms of Service, Version 1.0.
        </p>
      </Container>
    </main>
  );
}
