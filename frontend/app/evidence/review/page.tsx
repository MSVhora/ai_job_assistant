import type { Metadata } from "next";

import { ReviewPageClient } from "@/components/features/achievements/ReviewPageClient";

export const metadata: Metadata = {
  title: "Review achievements",
  description: "Review, edit, merge and approve achievements before they are used anywhere.",
};

export default function ReviewPage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-white" />
      </div>
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 pt-6 pb-12 sm:px-6">
        <section className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
            Review your{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              achievements
            </span>
          </h1>
          <p className="max-w-2xl text-sm text-gray-600">
            Every claim links to its evidence. Only approved achievements are used for resumes and
            interview answers.
          </p>
        </section>
        <ReviewPageClient />
      </div>
    </main>
  );
}
