"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { MergeDiffPanel } from "@/components/features/profile/MergeDiffPanel";
import { DraftErrorCard } from "@/components/features/profile/DraftErrorCard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useProfile, useUpdateProfile } from "@/hooks/use-profiles";
import { useResumeDraft } from "@/hooks/use-resume-draft";

export function MergeMode({
  profileId,
  resumeId,
}: {
  profileId: string;
  resumeId: string;
}) {
  const router = useRouter();
  const profileQuery = useProfile(profileId);
  const draftQuery = useResumeDraft(resumeId);
  const updateProfile = useUpdateProfile();

  if (profileQuery.isPending || draftQuery.isPending) {
    return (
      <div className="h-96 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" aria-live="polite" />
    );
  }

  if (profileQuery.isError) {
    return (
      <Card title="Could not load the profile">
        <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
          {profileQuery.error.message}
        </p>
        <Button variant="secondary" onClick={() => void profileQuery.refetch()}>
          Retry
        </Button>
      </Card>
    );
  }

  if (draftQuery.isError) {
    return (
      <DraftErrorCard
        resumeId={resumeId}
        error={draftQuery.error}
        onResolved={() => void draftQuery.refetch()}
      />
    );
  }

  const profile = profileQuery.data;
  const draft = draftQuery.data;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          Merge draft into “{profile.name}”
        </h2>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Comparing the AI draft with the saved profile — nothing changes until you save.
        </p>
      </div>
      <MergeDiffPanel
        current={profile.structured_profile}
        draft={draft.draft_profile}
        isSaving={updateProfile.isPending}
        saveError={updateProfile.error?.message ?? null}
        savedRevisionSource={updateProfile.data?.last_revision?.source ?? null}
        onSave={(merged) =>
          updateProfile.mutate(
            {
              profileId,
              payload: { structured_profile: merged, source_resume_id: resumeId },
            },
            {
              onSuccess: () => {
                void router.replace(`/profile?profile=${profileId}`);
              },
            },
          )
        }
        onDiscard={() => void router.replace(`/profile?profile=${profileId}`)}
      />
      <Link href="/profile" className="text-sm text-gray-600 underline dark:text-gray-400">
        Back to all profiles
      </Link>
    </div>
  );
}
