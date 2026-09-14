"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { SearchResults } from "@/components/features/jobs/SearchResults";
import { RunBanner } from "@/components/features/jobs/RunBanner";
import { GlobalConfigModal, GlobalConfigTrigger } from "@/components/features/jobs/GlobalConfigModal";
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
import { useJobSearchStatus } from "@/hooks/use-job-search";
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
  const [searchId, setSearchId] = useState<string | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<MatchResponse | null>(null);
  const [filters, setFilters] = useState<MatchFilterValues>(DEFAULT_MATCH_FILTERS);
  const [configOpen, setConfigOpen] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlProfileId = searchParams.get("profile");
  const sources = useSources();
  const profiles = useProfiles();
  const profilesList = profiles.data ?? [];
  const fallbackProfileId =
    urlProfileId === null ? (profilesList[0]?.profile_id ?? null) : urlProfileId;
  const activeProfileId = fallbackProfileId;
  const runStatus = useJobSearchStatus(searchId, activeProfileId);
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
    setSearchId(null);
    setSelectedMatch(null);
    void router.replace(`/jobs?profile=${profileId}`);
  };

  const priority = usePrioritySetting(activeProfileId);
  const enabledSources = sources.data?.filter((source) => source.enabled) ?? [];
  const [selectedSources, setSelectedSources] = useState<string[] | null>(null);
  const effectiveSelectedSources = selectedSources ?? enabledSources.map((s) => s.name);

  const toggleSource = (name: string, checked: boolean) => {
    setSelectedSources((current) => {
      const base = current ?? enabledSources.map((s) => s.name);
      return checked
        ? base.includes(name)
          ? base
          : [...base, name]
        : base.filter((source) => source !== name);
    });
  };

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

  const enabled = sources.data.filter((source) => source.enabled);
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
        <div className="shrink-0 border-t border-gray-100 p-3">
          <GlobalConfigTrigger onClick={() => setConfigOpen(true)} />
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
        <RunBanner
          searchId={searchId}
          profileId={activeProfileId}
          onDismiss={() => {
            setSearchId(null);
          }}
        />
        <MatchList
          profileId={activeProfileId}
          selection={selection}
          priority={priority.value}
          filters={filters}
          onFiltersChange={changeFilters}
        />
        <SearchResults searchId={searchId} profileId={activeProfileId} status={runStatus.data?.status} />
      </div>

      {selectedMatch !== null && (
        <div className="scrollbar-hidden self-start xl:sticky xl:top-4 xl:h-[calc(100vh-13rem)] xl:overflow-y-auto">
          <JobDetailPanel match={selectedMatch} onClose={selection.clear} />
        </div>
      )}

      <GlobalConfigModal
        open={configOpen}
        onOpenChange={setConfigOpen}
        profilesPending={profiles.isPending}
        profilesError={profiles.isError}
        profilesList={profilesList}
        activeProfileId={activeProfileId}
        onSelectProfile={selectProfile}
        sources={enabled}
        selectedSources={effectiveSelectedSources}
        onToggleSource={toggleSource}
        onSearchStarted={(id) => {
          setSearchId(id);
          setConfigOpen(false);
        }}
      />
    </div>
  );
}
