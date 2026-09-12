import type { Metadata } from "next";
import Link from "next/link";

import { SetupChecklist } from "@/components/features/setup/SetupChecklist";
import { SourceList } from "@/components/features/setup/SourceList";
import { KeyIcon } from "@/components/features/setup/icons";

export const metadata: Metadata = {
  title: "Setup",
  description: "Add Gemini, Adzuna and Apify API keys to power AI features and job sources.",
};

export default function SetupPage() {
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
            <KeyIcon className="h-3.5 w-3.5" />
            One-time setup
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Connect your{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              API keys
            </span>
          </h1>
          <p className="max-w-xl text-base text-gray-600">
            Get a free key from each provider, paste it into your backend{" "}
            <code className="rounded bg-violet-50 px-1.5 py-0.5 font-mono text-xs text-violet-700 ring-1 ring-violet-200">
              .env
            </code>
            , and restart the API. This page checks live whether each key was detected — keys are
            never sent to or stored by the frontend.
          </p>
        </section>

        <SetupChecklist />
        <SourceList />

        <p className="text-center text-sm text-gray-600">
          Done setting up?{" "}
          <Link
            href="/upload"
            className="font-semibold text-violet-700 underline underline-offset-2 hover:text-violet-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Upload your resume
          </Link>{" "}
          to build your profile and find matched jobs.
        </p>
      </div>
    </main>
  );
}
