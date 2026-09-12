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
      <div className="h-96 animate-pulse rounded-3xl bg-white/60" aria-live="polite" />
    );
  }

  if (profileQuery.isError) {
    return (
      <Card title="Could not load the profile">
        <p role="alert" className="mb-3 text-sm text-red-700">
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
    <div className="flex flex-col gap-6">
      <div className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur">
        <h2 className="text-xl font-bold tracking-tight text-gray-900">
          Merge draft into “{profile.name}”
        </h2>
        <p className="mt-1 text-sm text-gray-600">
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
      <Link href="/profile" className="text-center text-sm font-medium text-gray-600 underline underline-offset-2 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600">
        Back to all profiles
      </Link>
    </div>
  );
}
