import { ProfilePageClient } from "@/components/features/profile/ProfilePageClient";
import type { Metadata } from "next";
import { Suspense } from "react";

export const metadata: Metadata = {
  title: "Profile review | AI Job Assistant",
  description: "Review and edit your AI-extracted profile before saving it.",
};

export default function ProfilePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          Profile review
        </h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Every correction is recorded in the revision audit trail when you save.
        </p>
      </div>
      <Suspense
        fallback={
          <div
            className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800"
            aria-live="polite"
          />
        }
      >
        <ProfilePageClient />
      </Suspense>
    </main>
  );
}
