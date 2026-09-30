import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/request-a-project")({
  beforeLoad: () => {
    throw redirect({ to: "/request" });
  },
});
