"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useJobSearchStatus } from "@/hooks/use-job-search";

const STATUS_LABELS: Record<string, string> = {
  pending: "Run queued…",
  running: "Searching sources…",
  succeeded: "Search finished",
  partial: "Search finished with warnings",
  failed: "Search failed",
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

  return (
    <Card
      title={
        <span aria-live="polite" className="flex items-center gap-2">
          {status.isPending || status.data === undefined
            ? "Loading run…"
            : (STATUS_LABELS[status.data.status] ?? status.data.status)}
          {active && (
            <span
              className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-600 border-t-transparent"
              aria-hidden="true"
            />
          )}
        </span>
      }
      action={
        !active && status.data !== undefined ? (
          <button
            type="button"
            onClick={onDismiss}
            className="rounded-lg px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            Dismiss
          </button>
        ) : undefined
      }
    >
      {status.isError && (
        <div>
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            Could not load the run status.
          </p>
          <button
            type="button"
            onClick={() => void status.refetch()}
            className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
          >
            Retry
          </button>
        </div>
      )}
      {status.data !== undefined && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {status.data.results.length === 0 && active
              ? "Sources are being queried — you can leave this page; the run keeps going."
              : `Queried ${status.data.results.length} source(s).`}
          </p>
          <ul className="flex flex-col gap-2">
            {status.data.results.map((outcome) => (
              <li
                key={outcome.source}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800"
              >
                <span className="font-medium text-gray-900 dark:text-gray-100">
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
                {outcome.status === "ok" && <span>{outcome.count} posting(s) stored</span>}
                {outcome.warning && (
                  <span className="text-amber-700 dark:text-amber-400">{outcome.warning}</span>
                )}
              </li>
            ))}
            {status.data.matching && (
              <li className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800">
                <span className="font-medium text-gray-900 dark:text-gray-100">matching</span>
                <Badge
                  variant={status.data.matching.status === "ok" ? "success" : "warn"}
                >
                  {status.data.matching.status}
                </Badge>
                {status.data.matching.status === "ok" && (
                  <span>
                    {status.data.matching.scored_count} posting(s) scored ·{" "}
                    {status.data.matching.rationale_count} rationale(s) · rerank tokens{" "}
                    {status.data.matching.rerank_prompt_tokens}+
                    {status.data.matching.rerank_completion_tokens}
                  </span>
                )}
                {status.data.matching.warning && (
                  <span className="text-amber-700 dark:text-amber-400">
                    {status.data.matching.warning}
                  </span>
                )}
              </li>
            )}
          </ul>
          {status.data.status === "succeeded" && (
            <p className="text-sm text-gray-700 dark:text-gray-300">
              Matches are ranked against the profile — see the ranked matches below. The
              why-this-matches rationale covers the top postings; it refreshes on the next
              search after profile changes.
            </p>
          )}
          {status.data.status === "failed" && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-400">
              Every source failed — nothing was ingested. Check the per-source warnings
              above (usually a missing or rejected API key), fix the configuration in{" "}
              <Link
                href="/setup"
                className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
              >
                setup
              </Link>
              , and start a new search.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
