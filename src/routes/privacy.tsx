import { createFileRoute } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export const Route = createFileRoute("/privacy")({
  component: PrivacyPage,
  head: () => ({
    meta: [
      { title: "Privacy information — Hami" },
      { name: "description", content: "How Hami handles information for online inquiries." },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
});

function PrivacyPage() {
  return (
    <main className="py-14 sm:py-20">
      <Container className="max-w-3xl">
        <Eyebrow>Privacy information · draft for owner approval</Eyebrow>
        <h1 className="mt-3 font-display text-title font-black tracking-tight text-fg">
          Your information and Hami inquiries
        </h1>
        <p className="mt-5 text-sm leading-7 text-muted">
          Hami’s online inquiry form is currently closed. This draft explains
          what would happen if the form is opened; do not submit private
          information through a closed form.
        </p>

        <div className="mt-10 grid gap-8 border-t border-line pt-8">
          <section>
            <h2 className="font-display text-xl font-bold tracking-tight text-fg">
              What an open inquiry form collects
            </h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              The form asks for an email address or phone number, your preferred
              reply method, destination, course or field, expected start
              timeline, budget range, and permission for Hami to review and
              respond to that inquiry. It records when and why you gave
              permission. It does not ask for passports, identity documents, or
              academic records.
            </p>
            <p className="mt-3 text-sm leading-7 text-muted">
              Hami also keeps a short-lived, keyed identifier and request count
              to limit repeated submissions. It is used for abuse prevention,
              not for advertising.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold tracking-tight text-fg">
              Why it is used and who can see it
            </h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              The information is used to let the owner review your request,
              contact you through the method you chose if a reply is authorized,
              prevent duplicate or abusive submissions, and honor a deletion or
              opt-out request. The owner can see the inquiry in the private
              owner console.
            </p>
            <p className="mt-3 text-sm leading-7 text-muted">
              Vercel hosts the website, Neon provides the database, and any
              configured email-delivery provider processes information needed
              to run the service. If an owner notification is sent by email,
              that email provider may process the contact details and inquiry
              information in the notification. Hami does not send an automatic
              reply to you.
            </p>
            <p className="mt-3 text-sm leading-7 text-muted">
              If you choose to book through Cal.com, the information you enter
              there is handled by Cal.com for that booking. Hami does not
              automatically send your inquiry details to Cal.com.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold tracking-tight text-fg">
              Retention and your choices
            </h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              An inquiry with no recorded response action is automatically
              erased 30 days after it is submitted. There is not yet an
              automatic maximum retention period for an inquiry with a
              recorded response action. The owner can erase contact details
              sooner.
            </p>
            <p className="mt-3 text-sm leading-7 text-muted">
              If the form is open and you receive a private one-time control
              code, you can use it to permanently opt out or delete your
              inquiry. Both choices erase the contact details and answers.
              Opting out keeps a keyed suppression value to prevent the same
              contact from being re-entered or contacted; deletion leaves only
              a minimal record that an erasure occurred.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-bold tracking-tight text-fg">
              No sale of personal information
            </h2>
            <p className="mt-3 text-sm leading-7 text-muted">
              Hami does not sell your personal information. Inquiry consent is
              for the inquiry you submitted, not marketing permission.
            </p>
          </section>
        </div>
      </Container>
    </main>
  );
}
