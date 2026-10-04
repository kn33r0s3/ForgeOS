import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/climb")({
  beforeLoad: () => {
    // The climb now lives on /about.
    // This route is archived — the file stays, but traffic goes to the canonical page.
    throw redirect({ to: "/about" });
  },
});
