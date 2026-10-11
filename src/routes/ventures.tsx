import { createFileRoute } from "@tanstack/react-router";
import { HamiPathways } from "@/components/layout/hami-pathways";
import { AreaView } from "@/components/pages/area-view";

export const Route = createFileRoute("/ventures")({
  component: () => (
    <main>
      <AreaView name="Ventures" />
      <HamiPathways current="ventures" />
    </main>
  ),
  head: () => ({ meta: [{ title: "Ventures — Hami" }] }),
});
