import type { Metadata } from "next";

import { JobsPageClient } from "@/components/features/jobs/JobsPageClient";

export const metadata: Metadata = {
  title: "Jobs — AI Job Assistant",
  description: "Search enabled job sources and watch the ingestion run live.",
};

export default function JobsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          Job search
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          A run only starts when you submit it — the query below is exactly what gets sent.
        </p>
      </div>
      <JobsPageClient />
    </main>
  );
}
