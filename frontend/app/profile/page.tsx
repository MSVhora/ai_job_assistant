import { ProfilePageClient } from "@/components/features/profile/ProfilePageClient";
import type { Metadata } from "next";
import { Suspense } from "react";

export const metadata: Metadata = {
  title: "Review your profile",
  description: "Review and edit your AI-extracted profile before saving it.",
};

export default function ProfilePage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-transparent" />
        <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-violet-300/40 blur-3xl" />
        <div className="absolute -right-24 top-32 h-72 w-72 rounded-full bg-fuchsia-300/30 blur-3xl" />
      </div>

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 pb-16 pt-14">
        <section className="flex flex-col items-center gap-3 text-center">
          <p className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-wide text-violet-700 shadow-sm shadow-violet-100">
            Step 2 of 2
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Review your{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              profile
            </span>
          </h1>
          <p className="max-w-xl text-base text-gray-600">
            Check the AI-extracted details, fix anything off, and save. Every correction is recorded in the revision audit trail.
          </p>
        </section>

        <Suspense
          fallback={
            <div
              className="h-64 animate-pulse rounded-3xl bg-white/60"
              aria-live="polite"
            />
          }
        >
          <ProfilePageClient />
        </Suspense>
      </div>
    </main>
  );
}
