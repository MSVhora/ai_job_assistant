"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { SearchResults } from "@/components/features/jobs/SearchResults";
import { RunBanners } from "@/components/features/jobs/RunBanners";
import { SearchStepperModal } from "@/components/features/jobs/SearchStepperModal";
import { DEFAULT_MATCH_FILTERS, type MatchFilterValues } from "@/hooks/use-matches";
import { MatchList, type MatchSelection } from "@/components/features/jobs/MatchList";
import { JobDetailPanel } from "@/components/features/jobs/JobDetailPanel";
import { JobsFilterSidebar } from "./JobsFilterSidebar";
import { JobsNotices } from "./JobsNotices";
import { NoSourcesEnabled, SourcesError, SourcesPending } from "./JobsSourceStates";
import { useProfiles } from "@/hooks/use-profiles";
import { usePrioritySetting } from "@/hooks/use-priority-setting";
import { useJobSearchStatus, useProfileSearches } from "@/hooks/use-job-search";
import { isRunActive } from "@/hooks/use-job-search";
import { useSetupCheck, useSources } from "@/hooks/use-setup";
import type { MatchResponse } from "@/lib/api";

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
  const fallbackProfileId = urlProfileId ?? profilesList[0]?.profile_id ?? null;
  const activeProfileId = fallbackProfileId;
  const selectedRunStatus = useJobSearchStatus(selectedSearchId, activeProfileId);
  const setup = useSetupCheck();
  const selection: MatchSelection = {
    match: selectedMatch,
    toggle: (match) => {
      setSelectedMatch((current) => (current?.id === match.id ? null : match));
    },
    clear: () => {
      setSelectedMatch(null);
    },
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
    router.replace(`/jobs?profile=${profileId}`);
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
    return <SourcesPending />;
  }

  if (sources.isError) {
    return (
      <SourcesError
        onRetry={() => {
          void sources.refetch();
        }}
      />
    );
  }

  if (enabled.length === 0) {
    return <NoSourcesEnabled />;
  }

  const unconfigured = sources.data.filter((source) => source.enabled && !source.is_configured);
  const setupWarnings = setup.data?.warnings ?? [];
  const layoutClassName =
    selectedMatch !== null
      ? "grid items-start gap-4 lg:h-[calc(100vh-13rem)] lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[320px_minmax(0,1fr)_minmax(300px,360px)]"
      : "grid items-start gap-4 lg:h-[calc(100vh-13rem)] lg:grid-cols-[320px_minmax(0,1fr)]";

  return (
    <div className={layoutClassName}>
      <JobsFilterSidebar
        profiles={{
          list: profilesList,
          activeId: activeProfileId,
          disabled: profiles.isPending || profiles.isError,
          onSelect: selectProfile,
        }}
        filters={filters}
        onChangeFilters={changeFilters}
        priority={priority}
        onStartSearch={() => {
          setSearchOpen(true);
        }}
      />

      <div className="scrollbar-hidden flex min-w-0 flex-col gap-4 self-start lg:sticky lg:top-4 lg:h-[calc(100vh-13rem)] lg:overflow-y-auto">
        <JobsNotices setupWarnings={setupWarnings} unconfigured={unconfigured} />
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
          priority={priority.listValue}
          filters={filters}
          onFiltersChange={changeFilters}
        />
        <SearchResults
          searchId={selectedSearchId ?? searches.data?.[0]?.search_id ?? null}
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
          setSearchIds((current) => [...current, searchId]);
          setSelectedSearchId(searchId);
          setSearchOpen(false);
        }}
      />
    </div>
  );
}
