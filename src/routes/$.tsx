import { createFileRoute, notFound } from "@tanstack/react-router";

export const Route = createFileRoute("/$")({
  beforeLoad: () => {
    throw notFound();
  },
  head: () => ({
    meta: [{ name: "robots", content: "noindex, nofollow" }],
  }),
});
