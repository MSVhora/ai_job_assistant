import Link from "next/link";

import { Card } from "@/components/ui/card";

export function SourcesPending() {
  return (
    <div
      className="h-48 animate-pulse rounded-3xl border border-gray-200 bg-white/60"
      aria-busy="true"
      aria-live="polite"
    />
  );
}

export function SourcesError({ onRetry }: { onRetry: () => void }) {
  return (
    <Card title="Job sources">
      <p className="text-sm text-red-700">Could not load the job sources from the backend.</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
      >
        Retry
      </button>
    </Card>
  );
}

export function NoSourcesEnabled() {
  return (
    <Card title="No sources enabled yet">
      <p className="text-sm text-gray-700">
        Enable at least one job source before searching.{" "}
        <Link
          href="/setup"
          className="font-medium text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Go to setup
        </Link>
      </p>
    </Card>
  );
}
