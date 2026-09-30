import { createFileRoute } from "@tanstack/react-router";
import { AreaView } from "@/components/pages/area-view";

export const Route = createFileRoute("/technology")({
  component: () => (
    <main>
      <AreaView name="Technology" />
    </main>
  ),
  head: () => ({ meta: [{ title: "Technology — Hami" }] }),
});
