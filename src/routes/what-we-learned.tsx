import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/what-we-learned")({
  beforeLoad: () => {
    throw redirect({ to: "/unknowns" });
  },
});
