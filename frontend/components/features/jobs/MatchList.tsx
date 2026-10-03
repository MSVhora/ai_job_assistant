"use client";

import { useState } from "react";

import { MatchCard } from "@/components/features/jobs/MatchCard";
import { MatchEmptyState } from "./MatchEmptyState";
import { MatchesError, MatchesPending, NoProfileState } from "./MatchListStates";
import { MatchPagination } from "./MatchPagination";
import { MatchStatusTabs, type MatchStatus } from "./MatchStatusTabs";
import { hasActiveFilters } from "@/components/features/jobs/MatchFilterPanel";
import { DEFAULT_MATCH_FILTERS, useMatches, type MatchFilterValues } from "@/hooks/use-matches";
import type { MatchResponse } from "@/lib/api";

const MATCH_PAGE_SIZE = 20;

export interface MatchSelection {
  match: MatchResponse | null;
  toggle: (match: MatchResponse) => void;
  clear: () => void;
}

function hasFiltersActive(filters: MatchFilterValues): boolean {
  return hasActiveFilters(filters);
}

export function MatchList({
  profileId,
  selection,
  priority,
  filters,
  onFiltersChange,
}: {
  profileId: string | null;
  selection: MatchSelection;
  priority: number | undefined;
  filters: MatchFilterValues;
  onFiltersChange: (filters: MatchFilterValues) => void;
}) {
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState<MatchStatus>("active");
  const matches = useMatches(profileId, {
    limit: MATCH_PAGE_SIZE,
    offset: page * MATCH_PAGE_SIZE,
    priority,
    status,
    ...filters,
  });
  const list = matches.data?.items ?? [];
  const total = matches.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / MATCH_PAGE_SIZE));

  function changePage(next: number) {
    setPage(next);
    selection.clear();
  }

  function changeStatus(next: MatchStatus) {
    setStatus(next);
    setPage(0);
    selection.clear();
  }

  if (profileId === null) {
    return <NoProfileState />;
  }

  if (matches.isPending) {
    return <MatchesPending />;
  }

  if (matches.isError) {
    return (
      <MatchesError
        message={matches.error.message}
        onRetry={() => {
          void matches.refetch();
        }}
      />
    );
  }

  const filtersActive = hasFiltersActive(filters);

  return (
    <section
      id="matches-top"
      aria-labelledby="matches-heading"
      aria-live="polite"
      className="flex min-h-0 scroll-mt-6 flex-col rounded-3xl border border-gray-200 bg-white shadow-lg shadow-gray-100"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 px-5 py-4 sm:px-6">
        <h2 id="matches-heading" className="text-lg font-bold tracking-tight text-gray-900">
          Ranked matches
          {total > 0 && (
            <span className="ml-2 rounded-full bg-violet-100 px-2.5 py-0.5 text-sm font-semibold text-violet-700">
              {total}
            </span>
          )}
        </h2>
        <span className="text-xs text-gray-500">
          Page {page + 1} of {pageCount}
        </span>
      </div>
      <MatchStatusTabs status={status} onChange={changeStatus} />
      <div className="scrollbar-hidden min-h-0 flex-1 overflow-y-auto p-5 sm:p-6">
        {list.length === 0 ? (
          <MatchEmptyState
            status={status}
            filtersActive={filtersActive}
            onClearFilters={() => {
              onFiltersChange({ ...DEFAULT_MATCH_FILTERS });
              setPage(0);
            }}
          />
        ) : (
          <>
            <ul
              className={`flex flex-col gap-3 transition-opacity${
                matches.isFetching ? "opacity-60" : ""
              }`}
            >
              {list.map((match, index) => (
                <MatchCard
                  key={match.id}
                  match={match}
                  rank={page * MATCH_PAGE_SIZE + index + 1}
                  profileId={profileId}
                  selected={selection.match?.id === match.id}
                  onOpenDetails={() => {
                    selection.toggle(match);
                  }}
                />
              ))}
            </ul>
            <p className="mt-4 text-xs text-gray-500">
              Scores blend vector similarity with AI fit ratings; the priority slider re-weights
              them live without re-calling the AI. &quot;Why this matches&quot; appears on the top
              postings and refreshes on the next search after profile changes.
            </p>
          </>
        )}
      </div>
      {pageCount > 1 && <MatchPagination page={page} pageCount={pageCount} onChange={changePage} />}
    </section>
  );
}
