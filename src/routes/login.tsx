import { useState, type FormEvent } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AUTH_PROVIDERS, authClient, authEnabled, signIn } from "@/lib/auth/client";
import { getAuthAvailability } from "@/lib/auth/availability";
import { requestSignupPermit } from "@/lib/auth/signup-gate.server";
import { useCurrentUserState } from "@/lib/auth/use-current-user";

export const Route = createFileRoute("/login")({
  component: LoginPage,
  loader: () => getAuthAvailability(),
  head: () => ({ meta: [{ title: "Sign in — Hami" }] }),
});

function LoginPage() {
  const navigate = useNavigate();
  const { googleConfigured, termsConfigured, termsUrl } = Route.useLoaderData();
  const { user, isPending } = useCurrentUserState();
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "sign-up") {
        const gate = await requestSignupPermit({
          data: { dateOfBirth, acceptedTerms },
        });
        if (!gate.eligible) {
          setError(signupGateMessage(gate.reason));
          return;
        }
      }
      const result =
        mode === "sign-up"
          ? await authClient.signUp.email({ name: name.trim(), email: email.trim(), password })
          : await authClient.signIn.email({ email: email.trim(), password });
      if (result.error) {
        setError(result.error.message || "Authentication failed. Check the details and try again.");
        return;
      }
      await navigate({ to: "/system" });
    } catch {
      setError("Authentication is unavailable right now. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function startSocialSignIn(providerId: "google") {
    setBusy(true);
    setError(null);
    try {
      if (mode === "sign-up") {
        const gate = await requestSignupPermit({
          data: { dateOfBirth, acceptedTerms },
        });
        if (!gate.eligible) {
          setError(signupGateMessage(gate.reason));
          setBusy(false);
          return;
        }
      }
      await signIn(providerId, {
        callbackURL: "/system",
        requestSignUp: mode === "sign-up",
      });
    } catch {
      setError("Google sign-in could not be started. Please try again.");
      setBusy(false);
    }
  }

  return (
    <main>
      <Container className="grid min-h-[65dvh] place-items-center py-12">
        <section className="card w-full max-w-lg p-6 sm:p-8" aria-labelledby="login-title">
          {isPending ? (
            <p className="text-sm text-dim" role="status">Checking your account…</p>
          ) : user ? (
            <>
              <p className="font-mono text-xs font-bold uppercase tracking-[0.16em] text-accent">Private account</p>
              <h1 id="login-title" className="mt-2 text-3xl font-black text-ink">You’re signed in</h1>
              <p className="mt-2 text-sm text-muted">Your private context is available only to your account.</p>
              <Link to="/system" className="link-arrow mt-5 inline-flex min-h-11 items-center font-bold text-accent">
                Go to personal context
              </Link>
            </>
          ) : !authEnabled ? (
            <p className="text-sm font-semibold text-danger" role="alert">Sign-in is unavailable in this app configuration.</p>
          ) : (
            <>
              <p className="font-mono text-xs font-bold uppercase tracking-[0.16em] text-accent">Hami account</p>
              <h1 id="login-title" className="mt-2 text-3xl font-black text-ink">
                {mode === "sign-up" ? "Create your account" : "Sign in"}
              </h1>
              <p className="mt-2 text-sm leading-6 text-muted">
                Account context is private to you. Authentication does not authorize sharing it.
              </p>

              <div className="mt-6 grid gap-2">
                {AUTH_PROVIDERS.map((provider) => (
                  <Button
                    key={provider.providerId}
                    type="button"
                    variant="secondary"
                    disabled={
                      busy ||
                      !googleConfigured ||
                      (mode === "sign-up" && !termsConfigured)
                    }
                    onClick={() => void startSocialSignIn(provider.providerId)}
                  >
                    Continue with {provider.label}
                  </Button>
                ))}
                {!googleConfigured ? (
                  <p className="text-xs text-muted">
                    Direct Google OAuth is not configured in this environment.
                  </p>
                ) : null}
              </div>

              <div className="my-5 flex items-center gap-3 text-xs font-bold uppercase tracking-wider text-dim">
                <span className="h-px flex-1 bg-line" />
                or use email
                <span className="h-px flex-1 bg-line" />
              </div>

              <form onSubmit={submit} className="grid gap-4">
                {mode === "sign-up" ? (
                  <label className="grid gap-1.5 text-sm font-bold text-ink">
                    Name
                    <Input value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" required maxLength={120} />
                  </label>
                ) : null}
                {mode === "sign-up" ? (
                  <label className="grid gap-1.5 text-sm font-bold text-ink">
                    Date of birth
                    <Input
                      type="date"
                      value={dateOfBirth}
                      onChange={(event) => setDateOfBirth(event.target.value)}
                      autoComplete="bday"
                      max={new Date().toISOString().slice(0, 10)}
                      required
                    />
                  </label>
                ) : null}
                <label className="grid gap-1.5 text-sm font-bold text-ink">
                  Email
                  <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required maxLength={320} />
                </label>
                <label className="grid gap-1.5 text-sm font-bold text-ink">
                  Password
                  <Input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
                    required
                    minLength={8}
                  />
                </label>
                {mode === "sign-up" && termsConfigured && termsUrl ? (
                  <label className="flex items-start gap-2 text-sm text-muted">
                    <input
                      type="checkbox"
                      checked={acceptedTerms}
                      onChange={(event) => setAcceptedTerms(event.target.checked)}
                      required
                    />
                    <span>
                      I have read and agree to Hami’s{" "}
                      <a href={termsUrl} target="_blank" rel="noreferrer" className="font-bold text-accent underline">
                        Terms
                      </a>
                      .
                    </span>
                  </label>
                ) : null}
                {mode === "sign-up" && !termsConfigured ? (
                  <p className="rounded-md border border-line p-3 text-sm text-muted" role="status">
                    Hami’s legal terms are not yet configured. New account creation is unavailable.
                  </p>
                ) : null}
                {error ? <p className="text-sm font-semibold text-danger" role="alert">{error}</p> : null}
                <Button
                  type="submit"
                  disabled={busy || (mode === "sign-up" && !termsConfigured)}
                >
                  {busy ? "Working…" : mode === "sign-up" ? "Create account" : "Sign in"}
                </Button>
              </form>

              <p className="mt-5 text-sm text-muted">
                {mode === "sign-up" ? "Already have an account?" : "New to Hami?"}{" "}
                <button
                  type="button"
                  className="font-bold text-accent underline underline-offset-2"
                  onClick={() => {
                    setError(null);
                    setMode((current) => current === "sign-up" ? "sign-in" : "sign-up");
                  }}
                >
                  {mode === "sign-up" ? "Sign in" : "Create an account"}
                </button>
              </p>
            </>
          )}
        </section>
      </Container>
    </main>
  );
}

function signupGateMessage(reason: string): string {
  switch (reason) {
    case "dob_required":
      return "Enter your date of birth to continue.";
    case "dob_invalid":
      return "Enter a valid date of birth that is not in the future.";
    case "under_18":
      return "Hami accounts are available only to people aged 18 or older.";
    case "terms_acceptance_required":
      return "Accept the current Hami terms to create an account.";
    case "terms_not_configured":
      return "Hami’s legal terms are not yet configured. New account creation is unavailable.";
    default:
      return "Account creation could not be verified. Please try again.";
  }
}
