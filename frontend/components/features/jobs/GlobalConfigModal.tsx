"use client";

import { Modal } from "@/components/ui/modal";
import { SearchForm } from "@/components/features/jobs/SearchForm";
import { SourceMultiSelect } from "@/components/features/jobs/SourceMultiSelect";
import { PrioritySlider } from "@/components/features/jobs/PrioritySlider";
import { selectStyles } from "@/components/features/jobs/MatchFilterPanel";
import type { PrioritySetting } from "@/hooks/use-priority-setting";
import type { SourceInfo } from "@/lib/api";
import Link from "next/link";

function GearIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9l2.1 2.1m9.9 9.9l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" />
    </svg>
  );
}

export function GlobalConfigTrigger({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-haspopup="dialog"
      className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-violet-300 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
    >
      <span className="inline-flex items-center gap-2">
        <GearIcon />
        Global configuration
      </span>
      <span className="block text-[11px] font-medium text-violet-100">
        Profile · priority · queries · sources
      </span>
    </button>
  );
}

export function GlobalConfigModal({
  open,
  onOpenChange,
  profilesPending,
  profilesError,
  profilesList,
  activeProfileId,
  onSelectProfile,
  sources,
  selectedSources,
  onToggleSource,
  priority,
  onSearchStarted,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profilesPending: boolean;
  profilesError: boolean;
  profilesList: { profile_id: string; name: string }[];
  activeProfileId: string | null;
  onSelectProfile: (profileId: string) => void;
  sources: SourceInfo[];
  selectedSources: string[];
  onToggleSource: (name: string, checked: boolean) => void;
  priority: PrioritySetting;
  onSearchStarted: (searchId: string) => void;
}) {
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Global configuration"
      description="Everything that defines a new search run — profile, priority, queries and sources. Changes apply immediately."
    >
      <div className="flex flex-col gap-6">
        <div className="grid gap-5 rounded-2xl border border-violet-100 bg-violet-50/40 p-4 sm:grid-cols-2">
          <ProfileSelector
            profiles={profilesList}
            activeProfileId={activeProfileId}
            disabled={profilesPending || profilesError}
            onSelect={onSelectProfile}
          />
          <div className="flex flex-col justify-center">
            <PrioritySlider
              value={priority.value ?? 2 / 3}
              onChange={priority.change}
              disabled={priority.disabled}
            />
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <SourceMultiSelect
            sources={sources}
            selected={selectedSources}
            onToggle={onToggleSource}
          />
          <div className="border-t border-gray-100" />
          <SearchForm
            sources={sources}
            profileId={activeProfileId}
            onStarted={onSearchStarted}
            selectedSources={selectedSources}
          />
        </div>
      </div>
    </Modal>
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
        className={selectStyles}
      >
        {profiles.map((profile) => (
          <option key={profile.profile_id} value={profile.profile_id}>
            {profile.name}
          </option>
        ))}
      </select>
      <p className="text-xs text-gray-500">
        The selected track seeds the queries, location and country below.
      </p>
    </div>
  );
}
