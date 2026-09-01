"use client";

import Link from "next/link";
import { useState } from "react";

import { FirstReview } from "@/components/features/profile/FirstReview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { DraftProfileResponse, ProfileSummary } from "@/lib/api";

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
    <Card title="Choose where this draft goes">
      <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
        The AI draft from this resume can be merged into one of your existing profiles — or
        saved as a new, independent profile. Nothing changes until you decide.
      </p>
      <ul className="mb-4 flex flex-col gap-3">
        {profiles.map((profile) => (
          <li
            key={profile.profile_id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-700"
          >
            <div className="flex flex-col">
              <Link
                href={`/profile?profile=${profile.profile_id}&resume=${draft.resume_id}`}
                className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
              >
                Merge into “{profile.name}”
              </Link>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Updated {new Date(profile.updated_at).toLocaleString()}
              </span>
            </div>
            <Badge variant="neutral">compare &amp; choose fields</Badge>
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-3">
        <Button onClick={() => setCreatingNew(true)}>Save as new profile</Button>
        <Link
          href="/profile"
          className="text-sm text-gray-600 underline dark:text-gray-400"
        >
          Cancel
        </Link>
      </div>
    </Card>
  );
}
