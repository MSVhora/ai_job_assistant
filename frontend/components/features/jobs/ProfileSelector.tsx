"use client";

import { Select } from "@/components/ui/select";
import type { ProfileSummary } from "@/lib/api";
import Link from "next/link";

export function ProfileSelector({
  profiles,
  activeProfileId,
  disabled,
  onSelect,
  hint = "The selected track seeds the AI-generated queries, location and country.",
  id = "jobs-profile",
}: {
  profiles: ProfileSummary[];
  activeProfileId: string | null;
  disabled: boolean;
  onSelect: (profileId: string) => void;
  hint?: string;
  id?: string;
}) {
  if (disabled || profiles.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-violet-200 bg-violet-50/50 p-3 text-xs text-gray-600">
        {disabled
          ? "Loading profiles…"
          : "No profile yet — select or create one before starting a search, because every run is scoped to its profile. "}
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
        htmlFor={id}
        className="text-xs font-semibold uppercase tracking-wide text-gray-500"
      >
        Searching as profile
      </label>
      <Select
        id={id}
        value={activeProfileId ?? ""}
        onChange={(event) => onSelect(event.target.value)}
      >
        {profiles.map((profile) => (
          <option key={profile.profile_id} value={profile.profile_id}>
            {profile.name}
          </option>
        ))}
      </Select>
      <p className="text-xs text-gray-500">{hint}</p>
    </div>
  );
}
