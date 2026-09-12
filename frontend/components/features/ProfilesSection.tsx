"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useDeleteProfile, useProfiles } from "@/hooks/use-profiles";

function ProfileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-4 w-4">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
    </svg>
  );
}

const sectionHeader = "mb-4 flex flex-wrap items-center justify-between gap-2";
const sectionTitle = "text-lg font-bold tracking-tight text-gray-900";
const sectionHint = "mb-4 text-sm text-gray-600";

export function ProfilesSection() {
  const profilesQuery = useProfiles();

  if (profilesQuery.isPending) {
    return (
      <Card title="Your profiles">
        <div className="h-16 animate-pulse rounded-lg bg-gray-200" aria-live="polite" />
      </Card>
    );
  }

  if (profilesQuery.isError) {
    return (
      <Card title="Your profiles">
        <p role="alert" className="mb-3 text-sm text-red-700">
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
        <p className={sectionHint}>No profiles yet — upload a resume and save its AI draft as your first profile.</p>
      </Card>
    );
  }

  return (
    <section aria-labelledby="profiles-heading" className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100">
      <h2 id="profiles-heading" className="sr-only">Your profiles</h2>
      <div className={sectionHeader}>
        <h3 className={sectionTitle}>Your profiles</h3>
        <Badge variant="neutral">{profiles.length}</Badge>
      </div>
      <p className={sectionHint}>Each profile is an independent track — edit, merge, and match it separately.</p>
      <ul className="flex flex-col gap-3">
        {profiles.map((profile) => (
          <ProfileRow
            key={profile.profile_id}
            profileId={profile.profile_id}
            name={profile.name}
            updatedLabel={new Date(profile.updated_at).toLocaleString()}
            sourceLabel={profile.source_resume_filename ? `from ${profile.source_resume_filename}` : null}
          />
        ))}
      </ul>
    </section>
  );
}

function ProfileRow({
  profileId,
  name,
  updatedLabel,
  sourceLabel,
}: {
  profileId: string;
  name: string;
  updatedLabel: string;
  sourceLabel: string | null;
}) {
  const [confirming, setConfirming] = useState(false);
  const deleteProfile = useDeleteProfile();

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-100 bg-gray-50/60 p-4 transition-colors hover:border-violet-200 hover:bg-violet-50/40">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
          <ProfileIcon />
        </span>
        <div className="min-w-0">
          <Link
            href={`/profile?profile=${profileId}`}
            className="block truncate font-semibold text-gray-900 hover:text-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            {name}
          </Link>
          <span className="block truncate text-xs text-gray-500">
            Updated {updatedLabel}
            {sourceLabel ? ` · ${sourceLabel}` : ""}
          </span>
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
        {confirming && deleteProfile.isError && (
          <p role="alert" className="max-w-xs text-right text-sm text-red-700">
            {deleteProfile.error.message}
          </p>
        )}
        <div className="flex items-center gap-2">
          {confirming ? (
            <>
              <Button
                variant="danger"
                className="rounded-full px-3 py-1 text-xs"
                disabled={deleteProfile.isPending}
                onClick={() => deleteProfile.mutate(profileId, { onSuccess: () => setConfirming(false) })}
              >
                {deleteProfile.isPending ? "Deleting…" : "Confirm delete"}
              </Button>
              <Button variant="secondary" className="rounded-full px-3 py-1 text-xs" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </>
          ) : (
            <Button variant="secondary" className="rounded-full px-3 py-1 text-xs" onClick={() => setConfirming(true)}>
              Delete
            </Button>
          )}
        </div>
      </div>
    </li>
  );
}
