import { createFileRoute } from "@tanstack/react-router";
import { Hero } from "@/components/home/hero";
import { GroupTeaser } from "@/components/home/group-teaser";
import { ServicesSection } from "@/components/home/services-section";
import { CapabilitiesSection } from "@/components/home/capabilities-section";
import { WorkflowSection } from "@/components/home/workflow-section";
import { ForgeOSSection } from "@/components/home/forgeos-section";
import { TrustSection } from "@/components/home/trust-section";
import { CtaBand } from "@/components/layout/cta-band";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  return (
    <main>
      <Hero />
      <GroupTeaser />
      <ServicesSection />
      <CapabilitiesSection />
      <WorkflowSection />
      <ForgeOSSection />
      <TrustSection />
      <CtaBand />
    </main>
  );
}
