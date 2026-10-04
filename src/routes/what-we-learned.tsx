import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/what-we-learned")({
  beforeLoad: () => {
    // Consolidated into /discoveries (nav "Research").
    // This route is archived — the file stays, but traffic goes to the canonical page.
    throw redirect({ to: "/discoveries" });
  },
});
