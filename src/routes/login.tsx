import { useState, type FormEvent } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Container } from "@/components/layout/container";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authClient, authEnabled, signIn } from "@/lib/auth/client";
import { GROK_PROVIDERS } from "@/lib/auth/providers";
import { useCurrentUserState } from "@/lib/auth/use-current-user";

export const Route = createFileRoute("/login")({
  component: LoginPage,
  head: () => ({ meta: [{ title: "Sign in — Hami" }] }),
});

function LoginPage() {
  const navigate = useNavigate();
  const { user, isPending } = useCurrentUserState();
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = mode === "sign-up"
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
                {GROK_PROVIDERS.map((provider) => (
                  <Button
                    key={provider.providerId}
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => void signIn(provider.providerId, { callbackURL: "/system" })}
                  >
                    Continue with {provider.label}
                  </Button>
                ))}
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
                {error ? <p className="text-sm font-semibold text-danger" role="alert">{error}</p> : null}
                <Button type="submit" disabled={busy}>
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
