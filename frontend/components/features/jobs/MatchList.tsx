"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Card } from "@/components/ui/card";
import { MatchCard } from "@/components/features/jobs/MatchCard";
import { MatchFilterBar } from "@/components/features/jobs/MatchFilterBar";
import { PrioritySlider } from "@/components/features/jobs/PrioritySlider";
import {
  DEFAULT_MATCH_FILTERS,
  DEFAULT_PRIORITY,
  useMatches,
  type MatchFilterValues,
} from "@/hooks/use-matches";
import { useProfile, useUpdatePreferences } from "@/hooks/use-profiles";

const MATCH_PAGE_SIZE = 50;
const PERSIST_DEBOUNCE_MS = 400;

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
  const [priorityOverride, setPriorityOverride] = useState<number | undefined>(undefined);
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const profile = useProfile(profileId);
  const updatePreferences = useUpdatePreferences();
  const storedPriority = profile.data?.preferences?.priority;
  const priority = priorityOverride ?? storedPriority;
  const matches = useMatches(profileId, {
    limit: MATCH_PAGE_SIZE,
    offset: 0,
    priority,
    ...filters,
  });

  function handlePriorityChange(value: number) {
    setPriorityOverride(value);
    if (persistTimer.current !== null) clearTimeout(persistTimer.current);
    const targetProfileId = profileId;
    persistTimer.current = setTimeout(() => {
      if (targetProfileId === null) return;
      updatePreferences.mutate(
        { profileId: targetProfileId, payload: { priority: value } },
        {
          onError: () => {
            toast.error("Couldn't save the preference — ranking reflects this session only.", {
              id: "preferences-save-failed",
            });
          },
        },
      );
    }, PERSIST_DEBOUNCE_MS);
  }

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

  if (matches.isPending) {
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
      <div className="mb-4 flex flex-col gap-4">
        <PrioritySlider
          value={priorityOverride ?? storedPriority ?? DEFAULT_PRIORITY}
          onChange={handlePriorityChange}
          disabled={profile.isPending}
        />
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
          <ul
            className={`flex flex-col gap-2 transition-opacity${
              matches.isFetching ? " opacity-60" : ""
            }`}
          >
            {list.map((match, index) => (
              <MatchCard key={match.id} match={match} rank={index + 1} />
            ))}
          </ul>
          <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
            Scores blend vector similarity with AI fit ratings; the priority slider re-weights
            them live without re-calling the AI. &quot;Why this matches&quot; appears on the top
            postings and refreshes on the next search after profile changes.
          </p>
        </>
      )}
    </Card>
  );
}
