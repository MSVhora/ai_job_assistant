"use client";

import Link from "next/link";
import { useState } from "react";

import { FirstReview } from "@/components/features/profile/FirstReview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DraftProfileResponse, ProfileSummary } from "@/lib/api";

function ProfileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-4 w-4">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
    </svg>
  );
}

function MergeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-4 w-4">
      <path d="M7 3v5c0 3 2 5 5 5h5" />
      <path d="M14 10l3 3-3 3" />
      <path d="M7 21v-5" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-4 w-4">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function TargetChooser({
  draft,
  profiles,
}: {
  draft: DraftProfileResponse;
  profiles: ProfileSummary[];
}) {
  const [creatingNew, setCreatingNew] = useState(false);

  if (creatingNew) {
    return <FirstReview draft={draft} />;
  }

  return (
    <section
      aria-labelledby="target-heading"
      className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur sm:p-8"
    >
      <h2 id="target-heading" className="text-xl font-bold tracking-tight text-gray-900">
        Choose where this draft goes
      </h2>
      <p className="mt-1.5 text-sm text-gray-600">
        Merge the AI draft into one of your existing profiles — or save it as a new, independent profile. Nothing changes until you decide.
      </p>

      {profiles.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-dashed border-violet-200 bg-violet-50/50 p-4 text-sm text-gray-600">
          No profiles yet — save this draft as a new profile to create your first one.
        </p>
      ) : (
        <ul className="mt-6 flex flex-col gap-3">
          {profiles.map((profile) => (
            <li key={profile.profile_id}>
              <Link
                href={`/profile?profile=${profile.profile_id}&resume=${draft.resume_id}`}
                className="group flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-100 bg-gray-50/60 p-4 transition-colors hover:border-violet-300 hover:bg-violet-50/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
              >
                <span className="flex min-w-0 items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
                    <ProfileIcon />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-semibold text-gray-900 group-hover:text-violet-700">
                      Merge into “{profile.name}”
                    </span>
                    <span className="block truncate text-xs text-gray-500">
                      Updated {new Date(profile.updated_at).toLocaleString()}
                    </span>
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <Badge variant="neutral">compare &amp; choose fields</Badge>
                  <MergeIcon />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-gray-100 pt-5">
        <Button
          onClick={() => setCreatingNew(true)}
          className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-5 py-2.5 font-semibold shadow-lg shadow-violet-200 hover:from-violet-700 hover:to-fuchsia-700"
        >
          <span className="inline-flex items-center gap-2">
            <PlusIcon />
            Save as new profile
          </span>
        </Button>
        <Link
          href="/profile"
          className="text-sm font-medium text-gray-600 underline underline-offset-2 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Cancel
        </Link>
      </div>
    </section>
  );
}
