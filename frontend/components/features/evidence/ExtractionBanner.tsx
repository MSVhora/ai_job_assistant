"use client";

import Link from "next/link";

import { useExtractionRun } from "@/hooks/use-extraction";
import { formatUsd } from "@/lib/format-cost";
import { viewExtraction } from "@/lib/evidence-progress";

export function ExtractionBanner({ runId }: { runId: string }) {
  const run = useExtractionRun(runId);
  if (run.data === undefined) {
    return (
      <p className="text-sm text-gray-500" aria-live="polite">
        Loading the extraction run…
      </p>
    );
  }
  const view = viewExtraction(run.data);
  return (
    <section
      aria-label="Extraction status"
      className="rounded-2xl border border-violet-200 bg-violet-50/70 p-4"
    >
      <p aria-live="polite" className="flex items-center gap-2 text-sm font-bold text-gray-900">
        {view.active && (
          <span
            className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-violet-600 border-t-transparent"
            aria-hidden="true"
          />
        )}
        {view.active
          ? `Extracting… ${view.done} of ${view.total} chunks`
          : view.status === "succeeded"
            ? "Extraction finished"
            : "Extraction failed"}
      </p>
      <p className="mt-1 text-xs text-gray-700">
        {view.achievements} drafts created
        {view.rejected > 0 && `, ${view.rejected} rejected by validation`}
        {view.failed > 0 && `, ${view.failed} chunks failed and will be retried next time`}
        {view.cached > 0 && `, ${view.cached} served from cache`}
        {view.costUsd !== null && ` · cost ${formatUsd(view.costUsd)}`}.
      </p>
      {view.error !== null && (
        <p role="alert" className="mt-1 text-xs text-red-800">
          {view.error}
        </p>
      )}
      {!view.active && view.achievements > 0 && (
        <Link
          href="/evidence/review"
          className="mt-2 inline-block rounded-full bg-violet-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-violet-700"
        >
          Review the drafts
        </Link>
      )}
    </section>
  );
}
