import { createFileRoute } from "@tanstack/react-router";
import { HamiPathways } from "@/components/layout/hami-pathways";
import { AreaView } from "@/components/pages/area-view";

export const Route = createFileRoute("/technology")({
  component: () => (
    <main>
      <AreaView name="Technology" />
      <HamiPathways current="technology" />
    </main>
  ),
  head: () => ({ meta: [{ title: "Technology — Hami" }] }),
});
