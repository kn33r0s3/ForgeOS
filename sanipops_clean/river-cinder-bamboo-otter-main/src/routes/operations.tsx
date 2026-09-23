import { createFileRoute } from "@tanstack/react-router";
import { AreaView } from "@/components/pages/area-view";

export const Route = createFileRoute("/operations")({
  component: () => (
    <main>
      <AreaView name="Operations" />
    </main>
  ),
  head: () => ({ meta: [{ title: "Operations — Sanip Ops" }] }),
});
