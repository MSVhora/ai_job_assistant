"use client";

import { Badge } from "@/components/ui/badge";
import type { ProfileSummary, SourceInfo } from "@/lib/api";

import { ProfileSelector } from "./ProfileSelector";

export function ProfileStep({
  profiles,
  activeProfileId,
  profilesPending,
  profilesError,
  onSelectProfile,
}: {
  profiles: ProfileSummary[];
  activeProfileId: string | null;
  profilesPending: boolean;
  profilesError: boolean;
  onSelectProfile: (profileId: string) => void;
}) {
  return (
    <fieldset aria-label="Step 1: profile" className="flex flex-col gap-3">
      <ProfileSelector
        profiles={profiles}
        activeProfileId={activeProfileId}
        disabled={profilesPending || profilesError}
        onSelect={onSelectProfile}
        id="stepper-profile"
        hint="Every search run is scoped to exactly one profile."
      />
    </fieldset>
  );
}

export function SourceStep({
  sources,
  selectedSourceId,
  error,
  onSelect,
}: {
  sources: SourceInfo[];
  selectedSourceId: string;
  error?: string | undefined;
  onSelect: (sourceId: string) => void;
}) {
  return (
    <fieldset aria-label="Step 2: source" className="flex flex-col gap-2">
      <legend className="text-xs font-semibold tracking-wide text-gray-500 uppercase">
        Search one source
      </legend>
      {sources.map((source) => (
        <label
          key={source.name}
          className={`flex cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition-colors focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-violet-600 ${
            selectedSourceId === source.name
              ? "border-violet-500 bg-violet-50 font-semibold text-violet-800"
              : "border-gray-300 bg-white text-gray-700 hover:border-violet-300"
          } ${source.is_configured ? "" : "cursor-not-allowed opacity-60"}`}
        >
          <input
            type="radio"
            name="wizard-source"
            className="accent-violet-600"
            disabled={!source.is_configured}
            checked={selectedSourceId === source.name}
            onChange={() => {
              onSelect(source.name);
            }}
            aria-label={`Search ${source.name}`}
          />
          <span>{source.name}</span>
          <Badge variant={source.is_official_api ? "official-api" : "third-party-scraper"}>
            {source.is_official_api ? "Official API" : "Third-party scraper"}
          </Badge>
          {!source.is_configured && (
            <span className="text-xs text-amber-800">API key missing — set it in setup</span>
          )}
        </label>
      ))}
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </fieldset>
  );
}
