"use client";

import Link from "next/link";
import { useState } from "react";

import { MatchCard } from "@/components/features/jobs/MatchCard";
import { hasActiveFilters } from "@/components/features/jobs/MatchFilterPanel";
import {
  DEFAULT_MATCH_FILTERS,
  useMatches,
  type MatchFilterValues,
} from "@/hooks/use-matches";
import type { MatchResponse } from "@/lib/api";

const MATCH_PAGE_SIZE = 20;

export type MatchSelection = {
  match: MatchResponse | null;
  toggle: (match: MatchResponse) => void;
  clear: () => void;
};

function hasFiltersActive(filters: MatchFilterValues): boolean {
  return hasActiveFilters(filters);
}

function ChevronLeftIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4">
      <path
        fillRule="evenodd"
        d="M12.7 5.3a1 1 0 010 1.4L9.4 10l3.3 3.3a1 1 0 11-1.4 1.4l-4-4a1 1 0 010-1.4l4-4a1 1 0 011.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4">
      <path
        fillRule="evenodd"
        d="M7.3 5.3a1 1 0 000 1.4l3.3 3.3-3.3 3.3a1 1 0 101.4 1.4l4-4a1 1 0 000-1.4l-4-4a1 1 0 00-1.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
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
  const [status, setStatus] = useState<"active" | "saved" | "dismissed" | "all">("active");
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

  function changeStatus(next: "active" | "saved" | "dismissed" | "all") {
    setStatus(next);
    setPage(0);
    selection.clear();
  }

  if (profileId === null) {
    return (
      <section
        aria-labelledby="matches-heading"
        className="rounded-3xl border border-dashed border-violet-200 bg-white/70 p-8 text-center shadow-lg shadow-gray-100"
      >
        <h2 id="matches-heading" className="text-lg font-bold tracking-tight text-gray-900">
          Ranked matches
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-gray-600">
          Matches rank stored postings against a profile.{" "}
          <Link
            href="/profile"
            className="font-semibold text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Create a profile
          </Link>{" "}
          or run a search — matches appear here after the run finishes.
        </p>
      </section>
    );
  }

  if (matches.isPending) {
    return (
      <div
        className="h-96 animate-pulse rounded-3xl border border-gray-200 bg-white/60"
        aria-busy="true"
        aria-live="polite"
      />
    );
  }

  if (matches.isError) {
    return (
      <section
        aria-labelledby="matches-heading"
        className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100"
      >
        <h2 id="matches-heading" className="text-lg font-bold tracking-tight text-gray-900">
          Ranked matches
        </h2>
        <p role="alert" className="mt-3 text-sm text-red-700">
          Could not load matches: {matches.error.message}
        </p>
        <button
          type="button"
          onClick={() => void matches.refetch()}
          className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Retry
        </button>
      </section>
    );
  }

  const filtersActive = hasFiltersActive(filters);

  return (
    <section
      id="matches-top"
      aria-labelledby="matches-heading"
      aria-live="polite"
      className="scroll-mt-6 flex min-h-0 flex-col rounded-3xl border border-gray-200 bg-white shadow-lg shadow-gray-100"
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
      <nav aria-label="Match views" className="flex gap-1.5 border-b border-gray-100 px-5 pb-3 sm:px-6">
        {(
          [
            ["active", "Active"],
            ["saved", "Saved"],
            ["dismissed", "Dismissed"],
            ["all", "All"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => changeStatus(value)}
            aria-pressed={status === value}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 ${
              status === value
                ? "bg-violet-600 text-white shadow-sm"
                : "text-gray-500 hover:bg-violet-50 hover:text-violet-700"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="scrollbar-hidden min-h-0 flex-1 overflow-y-auto p-5 sm:p-6">
        {list.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-violet-200 bg-violet-50/40 px-4 py-8 text-center">
            <p className="max-w-md text-sm text-gray-600">
              {status === "saved"
                ? "Nothing saved yet. Use Save on a match card to keep it here."
                : status === "dismissed"
                  ? "No dismissed matches. Dismissed matches are hidden from the default view."
                  : filtersActive
                    ? "No postings match the current filters. Clear them to see every ranked match for this profile."
                    : "No matches for this profile yet. Run a search to fetch postings — matches appear here when the run finishes."}
            </p>
            {filtersActive && status === "active" && (
              <button
                type="button"
                onClick={() => {
                  onFiltersChange({ ...DEFAULT_MATCH_FILTERS });
                  setPage(0);
                }}
                className="rounded-full border border-violet-300 bg-white px-4 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <>
            <ul
              className={`flex flex-col gap-3 transition-opacity${
                matches.isFetching ? " opacity-60" : ""
              }`}
            >
              {list.map((match, index) => (
                <MatchCard
                  key={match.id}
                  match={match}
                  rank={page * MATCH_PAGE_SIZE + index + 1}
                  profileId={profileId}
                  selected={selection.match?.id === match.id}
                  onOpenDetails={() => selection.toggle(match)}
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
      {pageCount > 1 && (
        <nav
          aria-label="Matches pagination"
          className="flex shrink-0 items-center justify-center gap-2 border-t border-gray-100 py-3"
        >
          <button
            type="button"
            onClick={() => changePage(page - 1)}
            disabled={page === 0}
            className="inline-flex items-center gap-1 rounded-full border border-gray-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-gray-700 transition-colors hover:border-violet-300 hover:text-violet-700 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            <ChevronLeftIcon />
            Previous
          </button>
          <span className="px-2 text-xs text-gray-500" aria-current="page">
            {page + 1} / {pageCount}
          </span>
          <button
            type="button"
            onClick={() => changePage(page + 1)}
            disabled={page >= pageCount - 1}
            className="inline-flex items-center gap-1 rounded-full border border-gray-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-gray-700 transition-colors hover:border-violet-300 hover:text-violet-700 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Next
            <ChevronRightIcon />
          </button>
        </nav>
      )}
    </section>
  );
}
