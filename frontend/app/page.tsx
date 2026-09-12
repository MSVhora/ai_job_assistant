import { AiParticles } from "@/components/features/AiParticles";
import { CompaniesSection } from "@/components/features/CompaniesSection";
import { FeaturesSection } from "@/components/features/FeaturesSection";
import { HeroSection } from "@/components/features/HeroSection";
import { HowItWorksSection } from "@/components/features/HowItWorksSection";
import { SiteFooter } from "@/components/features/SiteFooter";

export default function Home() {
  return (
    <main className="relative isolate flex min-h-screen w-full flex-col text-gray-900">
      <AiParticles />
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 -z-10 bg-[linear-gradient(180deg,#ede9fe_0%,#f5f3ff_16%,#fae8ff_38%,#ffffff_78%)]"
      />
      <div
        aria-hidden="true"
        className="dot-grid pointer-events-none fixed inset-x-0 top-0 -z-10 h-[900px]"
      />
      <HeroSection />
      <FeaturesSection />
      <CompaniesSection />
      <HowItWorksSection />
      <SiteFooter />
    </main>
  );
}
