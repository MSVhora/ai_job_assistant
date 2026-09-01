"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useDeleteProfile, useProfiles } from "@/hooks/use-profiles";

export function ProfilesSection() {
  const profilesQuery = useProfiles();
  const deleteProfile = useDeleteProfile();

  if (profilesQuery.isPending) {
    return (
      <Card title="Your profiles">
        <div className="h-16 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" aria-live="polite" />
      </Card>
    );
  }

  if (profilesQuery.isError) {
    return (
      <Card title="Your profiles">
        <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
          {profilesQuery.error.message}
        </p>
        <Button variant="secondary" onClick={() => void profilesQuery.refetch()}>
          Retry
        </Button>
      </Card>
    );
  }

  const profiles = profilesQuery.data;

  if (profiles.length === 0) {
    return (
      <Card title="Your profiles">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          No profiles yet — upload a resume and save its AI draft as your first profile.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Your profiles">
      <p className="mb-3 text-sm text-gray-600 dark:text-gray-400">
        Each profile is an independent track — edit, merge, and match it separately.
      </p>
      <ul className="flex flex-col gap-3">
        {profiles.map((profile) => (
          <ProfileRow
            key={profile.profile_id}
            profileId={profile.profile_id}
            name={profile.name}
            updatedLabel={new Date(profile.updated_at).toLocaleString()}
            sourceLabel={profile.source_resume_filename ? `from ${profile.source_resume_filename}` : null}
            deleting={deleteProfile.isPending && deleteProfile.variables === profile.profile_id}
          />
        ))}
      </ul>
    </Card>
  );
}

function ProfileRow({
  profileId,
  name,
  updatedLabel,
  sourceLabel,
  deleting,
}: {
  profileId: string;
  name: string;
  updatedLabel: string;
  sourceLabel: string | null;
  deleting: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const deleteProfile = useDeleteProfile();

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div className="flex flex-col">
        <Link
          href={`/profile?profile=${profileId}`}
          className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
        >
          {name}
        </Link>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          Updated {updatedLabel}
          {sourceLabel ? ` · ${sourceLabel}` : ""}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="neutral">profile</Badge>
        {confirming ? (
          <>
            <Button
              variant="danger"
              className="px-2 py-1"
              disabled={deleting}
              onClick={() => deleteProfile.mutate(profileId)}
            >
              {deleting ? "Deleting…" : "Confirm delete"}
            </Button>
            <Button variant="secondary" className="px-2 py-1" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <Button variant="secondary" className="px-2 py-1" onClick={() => setConfirming(true)}>
            Delete
          </Button>
        )}
      </div>
    </li>
  );
}
