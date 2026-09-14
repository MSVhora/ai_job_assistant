import type { Metadata } from "next";
import { Suspense } from "react";

import { JobsPageClient } from "@/components/features/jobs/JobsPageClient";

export const metadata: Metadata = {
  title: "Job openings",
  description: "Search enabled job sources and watch the ingestion run live.",
};

export default function JobsPage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-white" />
        <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-violet-300/40 blur-3xl" />
        <div className="absolute -right-24 top-32 h-72 w-72 rounded-full bg-fuchsia-300/30 blur-3xl" />
      </div>

      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5 px-4 pb-8 pt-6 sm:px-6">
        <section className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
            Find your next{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              match
            </span>
          </h1>
        </section>

        <Suspense
          fallback={
            <div className="h-64 animate-pulse rounded-3xl bg-white/60" aria-live="polite" />
          }
        >
          <JobsPageClient />
        </Suspense>
      </div>
    </main>
  );
}
