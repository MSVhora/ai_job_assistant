"use client";

import Link from "next/link";
import { useState } from "react";

import { Card } from "@/components/ui/card";
import { MatchCard } from "@/components/features/jobs/MatchCard";
import { MatchFilterBar } from "@/components/features/jobs/MatchFilterBar";
import { DEFAULT_MATCH_FILTERS, useMatches, type MatchFilterValues } from "@/hooks/use-matches";

const MATCH_PAGE_SIZE = 50;

function hasActiveFilters(filters: MatchFilterValues): boolean {
  return (
    filters.location !== undefined ||
    filters.remote_type !== undefined ||
    filters.job_type !== undefined ||
    filters.posted_within_days !== undefined
  );
}

export function MatchList({ profileId }: { profileId: string | null }) {
  const [filters, setFilters] = useState<MatchFilterValues>(DEFAULT_MATCH_FILTERS);
  const matches = useMatches(profileId, {
    limit: MATCH_PAGE_SIZE,
    offset: 0,
    ...filters,
  });

  if (profileId === null) {
    return (
      <Card title="Ranked matches">
        <p className="text-sm text-gray-700 dark:text-gray-300">
          Matches rank stored postings against a profile.{" "}
          <Link
            href="/profile"
            className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
          >
            Create a profile
          </Link>{" "}
          or run a search — matches appear here after the run finishes.
        </p>
      </Card>
    );
  }

  if (matches.isPending || matches.isFetching) {
    return (
      <div
        className="h-48 animate-pulse rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-800"
        aria-busy="true"
        aria-live="polite"
      />
    );
  }

  if (matches.isError) {
    return (
      <Card title="Ranked matches">
        <p role="alert" className="text-sm text-red-700 dark:text-red-400">
          Could not load matches: {matches.error.message}
        </p>
        <button
          type="button"
          onClick={() => void matches.refetch()}
          className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
        >
          Retry
        </button>
      </Card>
    );
  }

  const list = matches.data ?? [];
  const filtersActive = hasActiveFilters(filters);

  return (
    <Card
      title={
        <span aria-live="polite">
          Ranked matches{list.length > 0 ? ` — ${list.length}` : ""}
        </span>
      }
    >
      <div className="mb-4">
        <MatchFilterBar filters={filters} onChange={setFilters} />
      </div>
      {list.length === 0 ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-gray-700 dark:text-gray-300">
            {filtersActive
              ? "No postings match the current filters. Clear them to see every ranked match for this profile."
              : "No matches for this profile yet. Run a search to fetch postings — matches appear here when the run finishes."}
          </p>
          {filtersActive && (
            <button
              type="button"
              onClick={() => setFilters(DEFAULT_MATCH_FILTERS)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <>
          <ul className="flex flex-col gap-2">
            {list.map((match, index) => (
              <MatchCard key={match.id} match={match} rank={index + 1} />
            ))}
          </ul>
          <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
            Scores blend vector similarity with AI fit ratings; &quot;why this matches&quot;
            appears on the top postings and refreshes on the next search after profile changes.
          </p>
        </>
      )}
    </Card>
  );
}
