"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { SearchResults } from "@/components/features/jobs/SearchResults";
import { RunBanners } from "@/components/features/jobs/RunBanners";
import { wizardDebug } from "@/components/features/jobs/wizard-debug";
import { RebuildBanner } from "@/components/features/jobs/RebuildBanner";
import {
  SearchStepperModal,
  StartSearchButton,
} from "@/components/features/jobs/SearchStepperModal";
import {
  DEFAULT_MATCH_FILTERS,
  type MatchFilterValues,
} from "@/hooks/use-matches";
import { MatchList, type MatchSelection } from "@/components/features/jobs/MatchList";
import { JobDetailPanel } from "@/components/features/jobs/JobDetailPanel";
import { MatchFilterPanel } from "@/components/features/jobs/MatchFilterPanel";
import { ProfileSelector } from "@/components/features/jobs/ProfileSelector";
import { Card } from "@/components/ui/card";
import { useProfiles } from "@/hooks/use-profiles";
import { usePrioritySetting } from "@/hooks/use-priority-setting";
import { useJobSearchStatus, useProfileSearches } from "@/hooks/use-job-search";
import { isRunActive } from "@/hooks/use-job-search";
import { useSetupCheck, useSources } from "@/hooks/use-setup";
import type { MatchResponse } from "@/lib/api";

function FunnelIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <path d="M3 5h18l-7 8v5.5L10 20v-7z" />
    </svg>
  );
}

export function JobsPageClient() {
  const [searchIds, setSearchIds] = useState<string[]>([]);
  const [dismissedIds, setDismissedIds] = useState<string[]>([]);
  const [selectedSearchId, setSelectedSearchId] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [selectedMatch, setSelectedMatch] = useState<MatchResponse | null>(null);
  const [filters, setFilters] = useState<MatchFilterValues>(DEFAULT_MATCH_FILTERS);
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlProfileId = searchParams.get("profile");
  const sources = useSources();
  const profiles = useProfiles();
  const profilesList = profiles.data ?? [];
  const fallbackProfileId =
    urlProfileId === null ? (profilesList[0]?.profile_id ?? null) : urlProfileId;
  const activeProfileId = fallbackProfileId;
  const selectedRunStatus = useJobSearchStatus(selectedSearchId, activeProfileId);
  const setup = useSetupCheck();
  const selection: MatchSelection = {
    match: selectedMatch,
    toggle: (match) => setSelectedMatch((current) => (current?.id === match.id ? null : match)),
    clear: () => setSelectedMatch(null),
  };
  const changeFilters = (next: MatchFilterValues) => {
    setFilters(next);
    setSelectedMatch(null);
  };
  const selectProfile = (profileId: string) => {
    setSearchIds([]);
    setDismissedIds([]);
    setSelectedSearchId(null);
    setSelectedMatch(null);
    void router.replace(`/jobs?profile=${profileId}`);
  };

  // Persisted runs: banners for still-active runs are derived from the
  // profile's run list, so they survive a page refresh; posts of finished runs
  // only reappear in the results view via the most recent run fallback.
  const searches = useProfileSearches(activeProfileId);
  const persistedActiveIds = (searches.data ?? [])
    .filter((run) => isRunActive(run.status) && !dismissedIds.includes(run.search_id))
    .map((run) => run.search_id);
  const bannerIds = [...new Set([...persistedActiveIds, ...searchIds])];

  const priority = usePrioritySetting(activeProfileId);
  const enabled = sources.data?.filter((source) => source.enabled) ?? [];

  if (sources.isPending) {
    return (
      <div
        className="h-48 animate-pulse rounded-3xl border border-gray-200 bg-white/60"
        aria-busy="true"
        aria-live="polite"
      />
    );
  }

  if (sources.isError || sources.data === undefined) {
    return (
      <Card title="Job sources">
        <p className="text-sm text-red-700">
          Could not load the job sources from the backend.
        </p>
        <button
          type="button"
          onClick={() => void sources.refetch()}
          className="mt-3 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Retry
        </button>
      </Card>
    );
  }

  if (enabled.length === 0) {
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

  const unconfigured = sources.data.filter(
    (source) => source.enabled && !source.is_configured,
  );
  const setupWarnings = setup.data?.warnings ?? [];
  const layoutClassName =
    selectedMatch !== null
      ? "grid items-start gap-4 lg:h-[calc(100vh-13rem)] lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[320px_minmax(0,1fr)_minmax(300px,360px)]"
      : "grid items-start gap-4 lg:h-[calc(100vh-13rem)] lg:grid-cols-[320px_minmax(0,1fr)]";

  return (
    <div className={layoutClassName}>
      <aside
        aria-label="Job list filters"
        className="flex flex-col self-start overflow-hidden rounded-3xl border border-violet-100 bg-white/80 shadow-xl shadow-violet-100/60 backdrop-blur lg:sticky lg:top-4 lg:h-[calc(100vh-13rem)]"
      >
        <div className="flex shrink-0 items-center gap-2.5 border-b border-gray-100 px-5 py-4">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
            <FunnelIcon />
          </span>
          <div>
            <h2 className="text-base font-bold tracking-tight text-gray-900">Filters</h2>
            <p className="text-xs text-gray-500">Narrow the ranked list</p>
          </div>
        </div>
        <div className="scrollbar-hidden flex min-h-0 flex-1 grow flex-col gap-5 overflow-y-auto p-5">
          <section className="rounded-2xl border border-violet-100 bg-violet-50/40 p-3" aria-label="Profile scope">
            <ProfileSelector
              profiles={profilesList}
              activeProfileId={activeProfileId}
              disabled={profiles.isPending || profiles.isError}
              onSelect={selectProfile}
              id="filter-profile"
              hint="Every search run and the match list below are scoped to this profile."
            />
          </section>
          <MatchFilterPanel
            filters={filters}
            onChange={changeFilters}
            priority={priority}
          />
        </div>
        <div className="flex shrink-0 flex-col gap-2 border-t border-gray-100 p-3">
          <RebuildBanner profileId={activeProfileId} />
          <StartSearchButton
          onClick={() => {
            wizardDebug("start-search trigger clicked (page level)");
            setSearchOpen(true);
          }}
        />
        </div>
      </aside>

      <div className="scrollbar-hidden flex min-w-0 flex-col gap-4 self-start lg:sticky lg:top-4 lg:h-[calc(100vh-13rem)] lg:overflow-y-auto">
        {setupWarnings.length > 0 && (
          <Card title="Provider setup incomplete">
            <ul className="list-inside list-disc text-sm text-amber-800">
              {setupWarnings.map((warning) => (
                <li key={warning} role="alert">
                  {warning}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-sm text-gray-600">
              Fix this before your first search —{" "}
              <Link
                href="/setup"
                className="font-medium text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
              >
                go to setup
              </Link>
              .
            </p>
          </Card>
        )}
        {unconfigured.length > 0 && (
          <Card title="Sources missing their API key">
            <p role="alert" className="text-sm text-amber-800">
              Enabled but unconfigured: {unconfigured.map((source) => source.name).join(", ")}.
              Their searches will fail until the key is set in <code>.env</code> —{" "}
              <Link
                href="/setup"
                className="font-medium text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
              >
                go to setup
              </Link>
              .
            </p>
          </Card>
        )}
        <RunBanners
          searchIds={bannerIds}
          profileId={activeProfileId}
          onDismiss={(searchId) => {
            setDismissedIds((current) => [...current, searchId]);
            setSearchIds((current) => current.filter((id) => id !== searchId));
          }}
        />
        <MatchList
          profileId={activeProfileId}
          selection={selection}
          priority={priority.value}
          filters={filters}
          onFiltersChange={changeFilters}
        />
        <SearchResults
          searchId={selectedSearchId ?? (searches.data?.[0]?.search_id ?? null)}
          profileId={activeProfileId}
          status={selectedRunStatus.data?.status}
        />
      </div>

      {selectedMatch !== null && (
        <div className="scrollbar-hidden self-start xl:sticky xl:top-4 xl:h-[calc(100vh-13rem)] xl:overflow-y-auto">
          <JobDetailPanel match={selectedMatch} onClose={selection.clear} />
        </div>
      )}

      <SearchStepperModal
        open={searchOpen}
        onOpenChange={setSearchOpen}
        profilesPending={profiles.isPending}
        profilesError={profiles.isError}
        profilesList={profilesList}
        activeProfileId={activeProfileId}
        onSelectProfile={selectProfile}
        sources={enabled}
        onSearchStarted={(searchId) => {
          wizardDebug("onSearchStarted (page level)", { searchId, currentSearchIds: searchIds });
          setSearchIds((current) => [...current, searchId]);
          setSelectedSearchId(searchId);
          setSearchOpen(false);
        }}
      />
    </div>
  );
}
