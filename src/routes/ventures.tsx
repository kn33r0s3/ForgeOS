import { createFileRoute } from "@tanstack/react-router";
import { AreaView } from "@/components/pages/area-view";

export const Route = createFileRoute("/ventures")({
  component: () => (
    <main>
      <AreaView name="Ventures" />
    </main>
  ),
  head: () => ({ meta: [{ title: "Ventures — Forge" }] }),
});
