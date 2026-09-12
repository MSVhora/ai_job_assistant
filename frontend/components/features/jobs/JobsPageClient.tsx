"use client";

import Link from "next/link";
import { useState } from "react";

import { SearchForm } from "@/components/features/jobs/SearchForm";
import { SearchResults } from "@/components/features/jobs/SearchResults";
import { RunBanner } from "@/components/features/jobs/RunBanner";
import { MatchList, type MatchSelection } from "@/components/features/jobs/MatchList";
import { JobDetailPanel } from "@/components/features/jobs/JobDetailPanel";
import { selectStyles as SELECT_STYLES } from "@/components/features/jobs/MatchFilterBar";
import { Card } from "@/components/ui/card";
import { PrioritySlider } from "@/components/features/jobs/PrioritySlider";
import { useProfiles } from "@/hooks/use-profiles";
import { usePrioritySetting } from "@/hooks/use-priority-setting";
import { useJobSearchStatus } from "@/hooks/use-job-search";
import { useSetupCheck, useSources } from "@/hooks/use-setup";
import type { MatchResponse } from "@/lib/api";

function ProfileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-4 w-4">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
    </svg>
  );
}

export function JobsPageClient() {
  const [searchId, setSearchId] = useState<string | null>(null);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<MatchResponse | null>(null);
  const sources = useSources();
  const profiles = useProfiles();
  const runStatus = useJobSearchStatus(searchId);
  const setup = useSetupCheck();
  const selection: MatchSelection = {
    match: selectedMatch,
    toggle: (match) => setSelectedMatch((current) => (current?.id === match.id ? null : match)),
    clear: () => setSelectedMatch(null),
  };

  const profilesList = profiles.data ?? [];
  const activeProfileId = profileId ?? profilesList[0]?.profile_id ?? null;
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
          className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Retry
        </button>
      </Card>
    );
  }

  const enabled = sources.data.filter((source) => source.enabled);
  if (enabled.length === 0) {    return (
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
      ? "grid items-start gap-4 lg:h-[calc(100vh-2rem)] lg:grid-cols-[340px_minmax(0,1fr)] xl:grid-cols-[340px_minmax(0,1fr)_minmax(300px,360px)]"
      : "grid items-start gap-4 lg:h-[calc(100vh-2rem)] lg:grid-cols-[340px_minmax(0,1fr)]";

  return (
    <div className={layoutClassName}>
      <aside
        aria-label="Search configuration"
        className="flex flex-col self-start overflow-hidden rounded-3xl border border-violet-100 bg-white/80 shadow-xl shadow-violet-100/60 backdrop-blur lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)]"
      >
        <div className="flex shrink-0 items-center gap-2.5 border-b border-gray-100 px-5 py-4">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
            <ProfileIcon />
          </span>
          <div>
            <h2 className="text-base font-bold tracking-tight text-gray-900">Search setup</h2>
            <p className="text-xs text-gray-500">Profile, queries and filters</p>
          </div>
        </div>
        <div className="scrollbar-hidden flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-5">
          <ProfileSelector
            profiles={profilesList}
            activeProfileId={activeProfileId}
            disabled={profiles.isPending || profiles.isError}
            onSelect={setProfileId}
          />
          <div className="rounded-2xl border border-gray-100 bg-gray-50/60 p-3">
            <PrioritySlider
              value={priority.value ?? 2 / 3}
              onChange={priority.change}
              disabled={priority.disabled}
            />
          </div>
          <SearchForm
            sources={enabled}
            profileId={activeProfileId}
            onStarted={(id) => setSearchId(id)}
            selectedSources={effectiveSelectedSources}
          />
        </div>
      </aside>

      <div className="scrollbar-hidden flex min-w-0 flex-col gap-4 self-start lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:overflow-y-auto">
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
          onDismiss={() => {
            setSearchId(null);
          }}
        />
        <MatchList
          profileId={activeProfileId}
          selection={selection}
          priority={priority.value}
          sources={enabled}
          selectedSources={effectiveSelectedSources}
          onToggleSource={toggleSource}
        />
        <SearchResults searchId={searchId} status={runStatus.data?.status} />
      </div>

      {selectedMatch !== null && (
        <div className="scrollbar-hidden self-start xl:sticky xl:top-4 xl:h-[calc(100vh-2rem)] xl:overflow-y-auto">
          <JobDetailPanel match={selectedMatch} onClose={selection.clear} />
        </div>
      )}
    </div>
  );
}

function ProfileSelector({
  profiles,
  activeProfileId,
  disabled,
  onSelect,
}: {
  profiles: { profile_id: string; name: string }[];
  activeProfileId: string | null;
  disabled: boolean;
  onSelect: (profileId: string) => void;
}) {
  if (disabled || profiles.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-violet-200 bg-violet-50/50 p-3 text-xs text-gray-600">
        {disabled
          ? "Loading profiles…"
          : "No profile yet — searches run without one, but a profile seeds the queries. "}
        {!disabled &&
          profiles.length === 0 && (
            <Link
              href="/profile"
              className="font-semibold text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
            >
              Create a profile
            </Link>
          )}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor="jobs-profile"
        className="text-xs font-semibold uppercase tracking-wide text-gray-500"
      >
        Searching as profile
      </label>
      <select
        id="jobs-profile"
        value={activeProfileId ?? ""}
        onChange={(event) => onSelect(event.target.value)}
        className={SELECT_STYLES}
      >
        {profiles.map((profile) => (
          <option key={profile.profile_id} value={profile.profile_id}>
            {profile.name}
          </option>
        ))}
      </select>
      <p className="text-xs text-gray-500">
        The selected track seeds the queries, location, and country below.
      </p>
    </div>
  );
}
