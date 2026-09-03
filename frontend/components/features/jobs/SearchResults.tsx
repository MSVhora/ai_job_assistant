"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { isRunFinished, useSearchPostings } from "@/hooks/use-job-search";
import { salaryLine } from "@/lib/salary";

export function SearchResults({ searchId, status }: { searchId: string | null; status: string | undefined }) {
  const finished = isRunFinished(status);
  const postings = useSearchPostings(searchId, finished);

  if (searchId === null || !finished) return null;

  if (postings.isPending || postings.isFetching) {
    return (
      <div
        className="h-40 animate-pulse rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-800"
        aria-busy="true"
        aria-live="polite"
      />
    );
  }

  if (postings.isError) {
    return (
      <Card title="Results">
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          Could not load the results of this run.
        </p>
        <button
          type="button"
          onClick={() => void postings.refetch()}
          className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
        >
          Retry
        </button>
      </Card>
    );
  }

  const list = postings.data ?? [];
  if (list.length === 0) {
    if (status === "failed") {
      return (
        <Card title="Search failed">
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            The run failed before any source could return postings — see the run banner
            above for the per-source warnings. Fix the configuration and start a new
            search.
          </p>
        </Card>
      );
    }
    return (
      <Card title="No postings from this run">
        <p className="text-sm text-gray-700 dark:text-gray-300">
          The sources returned nothing for these queries and filters. Try broadening the
          title or skills, lowering or clearing the minimum salary (Adzuna&apos;s salary
          coverage is thin in some countries), or widening the location.
        </p>
      </Card>
    );
  }

  return (
    <Card
      title={
        <span aria-live="polite">
          Results — {list.length} posting{list.length === 1 ? "" : "s"}
        </span>
      }
    >
      <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">
        Unranked, as returned by the sources — the ranked view with the why-this-matches
        rationale is above.
      </p>
      <ul className="flex flex-col gap-2">
        {list.map((posting) => {
          const salary = salaryLine(posting.salary_min, posting.salary_max, posting.currency);
          return (
            <li
              key={posting.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800"
            >
              <Badge variant={posting.source.startsWith("apify") ? "third-party-scraper" : "official-api"}>
                {posting.source}
              </Badge>
              {posting.url ? (
                <a
                  href={posting.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
                >
                  {posting.title}
                </a>
              ) : (
                <span className="font-medium text-gray-900 dark:text-gray-100">{posting.title}</span>
              )}
              {posting.company && (
                <span className="text-gray-700 dark:text-gray-300">{posting.company}</span>
              )}
              {posting.location && (
                <span className="text-gray-500 dark:text-gray-400">{posting.location}</span>
              )}
              {salary && <span className="text-gray-700 dark:text-gray-300">{salary}</span>}
              {posting.posted_at && (
                <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">
                  {new Date(posting.posted_at).toLocaleDateString()}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
