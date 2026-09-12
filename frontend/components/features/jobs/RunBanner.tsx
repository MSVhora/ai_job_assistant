"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { useJobSearchStatus } from "@/hooks/use-job-search";

const STATUS_LABELS: Record<string, string> = {
  pending: "Run queued…",
  running: "Searching sources…",
  succeeded: "Search finished",
  partial: "Search finished with warnings",
  failed: "Search failed",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "border-violet-200 bg-violet-50/80",
  running: "border-violet-200 bg-violet-50/80",
  succeeded: "border-emerald-200 bg-emerald-50/80",
  partial: "border-amber-200 bg-amber-50/80",
  failed: "border-red-200 bg-red-50/80",
};

export function RunBanner({
  searchId,
  onDismiss,
}: {
  searchId: string | null;
  onDismiss: () => void;
}) {
  const status = useJobSearchStatus(searchId);

  if (searchId === null) return null;

  const active = status.isPending || (status.data?.status === "pending" || status.data?.status === "running");
  const tone = status.data !== undefined ? (STATUS_STYLES[status.data.status] ?? "border-gray-200 bg-white") : "border-violet-200 bg-violet-50/80";

  return (
    <section
      aria-label="Run status"
      className={`rounded-3xl border p-5 shadow-lg shadow-gray-100 ${tone}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span aria-live="polite" className="flex items-center gap-2.5 text-base font-bold tracking-tight text-gray-900">
          {active && (
            <span
              className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-violet-600 border-t-transparent"
              aria-hidden="true"
            />
          )}
          {status.isPending || status.data === undefined
            ? "Loading run…"
            : (STATUS_LABELS[status.data.status] ?? status.data.status)}
        </span>
        {!active && status.data !== undefined && (
          <button
            type="button"
            onClick={onDismiss}
            className="rounded-full px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-white hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Dismiss
          </button>
        )}
      </div>

      {status.isError && (
        <div className="mt-3">
          <p role="alert" className="text-sm text-red-700">
            Could not load the run status.
          </p>
          <button
            type="button"
            onClick={() => void status.refetch()}
            className="mt-2 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Retry
          </button>
        </div>
      )}
      {status.data !== undefined && (
        <div className="mt-3 flex flex-col gap-2">
          <p className="text-sm text-gray-600">
            {status.data.results.length === 0 && active
              ? "Sources are being queried — you can leave this page; the run keeps going."
              : `Queried ${status.data.results.length} source(s).`}
          </p>
          <ul className="flex flex-col gap-1.5">
            {status.data.results.map((outcome) => (
              <li
                key={outcome.source}
                className="flex flex-wrap items-center gap-2 rounded-xl border border-white bg-white/80 px-3 py-2 text-sm shadow-sm"
              >
                <span className="font-semibold text-gray-900">
                  {outcome.source}
                </span>
                <Badge
                  variant={
                    outcome.status === "ok"
                      ? "success"
                      : (outcome.status === "failed" ? "danger" : "warn")
                  }
                >
                  {outcome.status}
                </Badge>
                {outcome.status === "ok" && <span className="text-gray-600">{outcome.count} posting(s) stored</span>}
                {outcome.warning && (
                  <span className="text-amber-700">{outcome.warning}</span>
                )}
              </li>
            ))}
            {status.data.matching && (
              <li className="flex flex-wrap items-center gap-2 rounded-xl border border-white bg-white/80 px-3 py-2 text-sm shadow-sm">
                <span className="font-semibold text-gray-900">matching</span>
                <Badge
                  variant={status.data.matching.status === "ok" ? "success" : "warn"}
                >
                  {status.data.matching.status}
                </Badge>
                {status.data.matching.status === "ok" && (
                  <span className="text-gray-600">
                    {status.data.matching.scored_count} posting(s) scored ·{" "}
                    {status.data.matching.rationale_count} rationale(s) · rerank tokens{" "}
                    {status.data.matching.rerank_prompt_tokens}+
                    {status.data.matching.rerank_completion_tokens}
                  </span>
                )}
                {status.data.matching.warning && (
                  <span className="text-amber-700">
                    {status.data.matching.warning}
                  </span>
                )}
              </li>
            )}
          </ul>
          {status.data.status === "succeeded" && (
            <p className="text-sm text-gray-700">
              Matches are ranked against the profile — see the ranked matches below. The
              why-this-matches rationale covers the top postings; it refreshes on the next
              search after profile changes.
            </p>
          )}
          {status.data.status === "failed" && (
            <p role="alert" className="text-sm text-red-700">
              Every source failed — nothing was ingested. Check the per-source warnings
              above (usually a missing or rejected API key), fix the configuration in{" "}
              <Link
                href="/setup"
                className="font-semibold text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
              >
                setup
              </Link>
              , and start a new search.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
