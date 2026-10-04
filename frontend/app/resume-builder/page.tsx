import type { Metadata } from "next";
import { Suspense } from "react";

import { ResumeBuilderPageClient } from "@/components/features/resume/ResumeBuilderPageClient";

export const metadata: Metadata = {
  title: "Resume builder",
  description:
    "Build a resume from your approved achievements, review it as text, then generate a PDF.",
};

export default function ResumeBuilderPage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-white" />
      </div>
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 pt-6 pb-12 sm:px-6">
        <section className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
            Resume{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              builder
            </span>
          </h1>
          <p className="max-w-2xl text-sm text-gray-600">
            Choose a length, optionally tailor to a job, and review the written content before any
            PDF exists. Every bullet is checked against your evidence.
          </p>
        </section>
        <Suspense fallback={<div className="h-64 animate-pulse rounded-3xl bg-white/60" />}>
          <ResumeBuilderPageClient />
        </Suspense>
      </div>
    </main>
  );
}
