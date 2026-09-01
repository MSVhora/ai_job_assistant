import type { Metadata } from "next";

import { KeyStatusCards } from "@/components/features/setup/KeyStatusCards";
import { SourceList } from "@/components/features/setup/SourceList";

export const metadata: Metadata = {
  title: "Setup — AI Job Assistant",
  description: "Provider keys and job-source enablement with disclosure acknowledgment.",
};

export default function SetupPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          Setup
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Keys are configured in your backend <code>.env</code> — this page reports what the
          backend detected. Scraping sources must be acknowledged before they can run.
        </p>
      </div>
      <KeyStatusCards />
      <SourceList />
    </main>
  );
}
