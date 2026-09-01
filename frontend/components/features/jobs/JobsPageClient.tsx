"use client";

import Link from "next/link";
import { useState } from "react";

import { SearchForm } from "@/components/features/jobs/SearchForm";
import { RunBanner } from "@/components/features/jobs/RunBanner";
import { Card } from "@/components/ui/card";
import { useSources } from "@/hooks/use-setup";
import { useProfiles } from "@/hooks/use-profiles";

export function JobsPageClient() {
  const [searchId, setSearchId] = useState<string | null>(null);
  const [profileId, setProfileId] = useState<string | null>(null);
  const sources = useSources();
  const profiles = useProfiles();

  if (sources.isPending) {
    return (
      <div
        className="h-48 animate-pulse rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-800"
        aria-busy="true"
        aria-live="polite"
      />
    );
  }

  if (sources.isError || sources.data === undefined) {
    return (
      <Card title="Job sources">
        <p className="text-sm text-red-700 dark:text-red-400">
          Could not load the job sources from the backend.
        </p>
        <button
          type="button"
          onClick={() => void sources.refetch()}
          className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
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
        <p className="text-sm text-gray-700 dark:text-gray-300">
          Enable at least one job source before searching.{" "}
          <Link
            href="/setup"
            className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
          >
            Go to setup
          </Link>
        </p>
      </Card>
    );
  }

  const profilesList = profiles.data ?? [];
  const activeProfileId = profileId ?? profilesList[0]?.profile_id ?? null;

  return (
    <div className="flex flex-col gap-6">
      <ProfileSelector
        profiles={profilesList}
        activeProfileId={activeProfileId}
        disabled={profiles.isPending || profiles.isError}
        onSelect={setProfileId}
      />
      <SearchForm
        sources={enabled}
        profileId={activeProfileId}
        onStarted={(id) => setSearchId(id)}
      />
      <RunBanner
        searchId={searchId}
        onDismiss={() => {
          setSearchId(null);
        }}
      />
    </div>
  );
}

const SELECT_STYLES =
  "w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100";

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
      <p className="text-sm text-gray-600 dark:text-gray-400">
        {disabled
          ? "Loading profiles…"
          : "No profile yet — searches run without one, but a profile seeds the query. "}
        {!disabled &&
          profiles.length === 0 && (
            <Link
              href="/profile"
              className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
            >
              Create a profile
            </Link>
          )}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor="jobs-profile"
        className="text-sm font-medium text-gray-800 dark:text-gray-200"
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
      <p className="text-xs text-gray-500 dark:text-gray-400">
        The selected track seeds the query, location, and country below.
      </p>
    </div>
  );
}
