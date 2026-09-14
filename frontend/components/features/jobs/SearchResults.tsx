"use client";

import { Badge } from "@/components/ui/badge";
import { FreshnessBadge } from "@/components/features/jobs/FreshnessBadge";
import { isRunFinished, useSearchPostings } from "@/hooks/use-job-search";
import { salaryLine } from "@/lib/salary";

export function SearchResults({
  searchId,
  profileId,
  status,
}: {
  searchId: string | null;
  profileId: string | null;
  status: string | undefined;
}) {
  const finished = isRunFinished(status);
  const postings = useSearchPostings(searchId, profileId, finished);

  if (searchId === null || !finished) return null;

  if (postings.isPending || postings.isFetching) {
    return (
      <div
        className="h-40 animate-pulse rounded-3xl border border-gray-200 bg-white/60"
        aria-busy="true"
        aria-live="polite"
      />
    );
  }

  if (postings.isError) {
    return (
      <section aria-labelledby="results-heading" className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100">
        <h2 id="results-heading" className="text-lg font-bold tracking-tight text-gray-900">Results</h2>
        <p role="alert" className="mt-3 text-sm text-red-700">
          Could not load the results of this run.
        </p>
        <button
          type="button"
          onClick={() => void postings.refetch()}
          className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Retry
        </button>
      </section>
    );
  }

  const list = postings.data ?? [];
  if (list.length === 0) {
    if (status === "failed") {
      return (
        <section aria-labelledby="results-heading" className="rounded-3xl border border-red-200 bg-red-50/60 p-6">
          <h2 id="results-heading" className="text-lg font-bold tracking-tight text-gray-900">Search failed</h2>
          <p role="alert" className="mt-2 text-sm text-red-700">
            The run failed before any source could return postings — see the run banner
            above for the per-source warnings. Fix the configuration and start a new
            search.
          </p>
        </section>
      );
    }
    return (
      <section aria-labelledby="results-heading" className="rounded-3xl border border-dashed border-violet-200 bg-white/70 p-6">
        <h2 id="results-heading" className="text-lg font-bold tracking-tight text-gray-900">No postings from this run</h2>
        <p className="mt-2 text-sm text-gray-600">
          The sources returned nothing for these queries and filters. Try broadening the
          title or skills, lowering or clearing the minimum salary (Adzuna&apos;s salary
          coverage is thin in some countries), or widening the location.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="results-heading" className="rounded-3xl border border-gray-200 bg-white p-5 shadow-lg shadow-gray-100 sm:p-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="results-heading" aria-live="polite" className="text-lg font-bold tracking-tight text-gray-900">
          Results
          <span className="ml-2 rounded-full bg-gray-100 px-2.5 py-0.5 text-sm font-semibold text-gray-600">
            {list.length} posting{list.length === 1 ? "" : "s"}
          </span>
        </h2>
      </div>
      <p className="mb-3 text-xs text-gray-500">
        Unranked, as returned by the sources — the ranked view with the why-this-matches
        rationale is above.
      </p>
      <ul className="flex flex-col gap-2">
        {list.map((posting) => {
          const salary = salaryLine(posting.salary_min, posting.salary_max, posting.currency);
          return (
            <li
              key={posting.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl border border-gray-100 bg-gray-50/60 px-3.5 py-2.5 text-sm transition-colors hover:border-violet-200 hover:bg-violet-50/40"
            >
              <Badge variant={posting.source.startsWith("apify") ? "third-party-scraper" : "official-api"}>
                {posting.source}
              </Badge>
              <FreshnessBadge expiresAt={posting.expires_at} postedAt={posting.posted_at} />
              {posting.url ? (
                <a
                  href={posting.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-semibold text-gray-900 hover:text-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
                >
                  {posting.title}
                </a>
              ) : (
                <span className="font-semibold text-gray-900">{posting.title}</span>
              )}
              {posting.company && (
                <span className="text-gray-700">{posting.company}</span>
              )}
              {posting.location && (
                <span className="text-gray-500">{posting.location}</span>
              )}
              {salary && <span className="font-medium text-gray-800">{salary}</span>}
              {posting.posted_at && (
                <span className="ml-auto text-xs text-gray-500">
                  {new Date(posting.posted_at).toLocaleDateString()}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
