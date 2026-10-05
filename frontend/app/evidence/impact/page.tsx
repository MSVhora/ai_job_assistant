import type { Metadata } from "next";
import Link from "next/link";

import { ImpactQueueClient } from "@/components/features/achievements/ImpactQueueClient";

export const metadata: Metadata = {
  title: "Add impact",
  description: "Add the real numbers behind your strongest achievements.",
};

export default function ImpactPage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-white" />
      </div>
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-5 px-4 pt-6 pb-12 sm:px-6">
        <section className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
            Add the{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              impact
            </span>
          </h1>
          <p className="text-sm text-gray-600">
            Commits rarely say what a change was worth. Your strongest achievements without a
            confirmed number come first; a real figure moves them up on your resume.
          </p>
          <Link href="/evidence/review" className="text-sm font-semibold text-violet-700 underline">
            Back to review
          </Link>
        </section>
        <ImpactQueueClient />
      </div>
    </main>
  );
}
