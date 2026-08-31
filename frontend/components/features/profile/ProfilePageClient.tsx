"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ProfileReviewForm } from "@/components/features/profile/ProfileReviewForm";
import { MergeDiffPanel } from "@/components/features/profile/MergeDiffPanel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FormProvider, useForm } from "react-hook-form";
import { useProfile } from "@/hooks/use-profile";
import { useResumeDraft } from "@/hooks/use-resume-draft";
import { useSaveProfile } from "@/hooks/use-save-profile";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { profileFormSchema } from "@/lib/profile-schema";
import { toFormValues } from "@/lib/profile-schema";
import type { StructuredProfile } from "@/lib/api";

function ProfileFormShell({
  profile,
  highlightAi,
}: {
  profile: StructuredProfile;
  highlightAi: boolean;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resumeId = searchParams.get("resume");
  const saveProfile = useSaveProfile();
  const form = useForm({
    resolver: standardSchemaResolver(profileFormSchema),
    defaultValues: toFormValues(profile),
    mode: "onBlur",
  });

  return (
    <FormProvider {...form}>
      <ProfileReviewForm
        highlightAi={highlightAi}
        isSaving={saveProfile.isPending}
        saveError={saveProfile.error?.message ?? null}
        savedRevisionSource={saveProfile.data?.last_revision?.source ?? null}
        onSave={(structured) =>
          saveProfile.mutate(
            { structured_profile: structured, source_resume_id: resumeId },
            {
              onSuccess: () => {
                void router.replace("/profile");
              },
            },
          )
        }
      />
    </FormProvider>
  );
}

export function ProfilePageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resumeId = searchParams.get("resume");
  const profileQuery = useProfile();
  const draftQuery = useResumeDraft(resumeId);
  const saveProfile = useSaveProfile();

  if (profileQuery.isPending || (resumeId !== null && draftQuery.isPending)) {
    return (
      <div className="flex flex-col gap-4" aria-live="polite">
        <div className="h-8 w-64 animate-pulse rounded-md bg-gray-200 dark:bg-gray-800" />
        <div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
        <div className="h-64 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
      </div>
    );
  }

  if (profileQuery.isError) {
    return (
      <Card title="Could not load your profile">
        <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
          {profileQuery.error.message}
        </p>
        <Button variant="secondary" onClick={() => void profileQuery.refetch()}>
          Retry
        </Button>
      </Card>
    );
  }

  if (resumeId !== null && draftQuery.isError) {
    return (
      <Card title="Could not load the extracted draft">
        <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
          {draftQuery.error.message}
        </p>
        <Button variant="secondary" onClick={() => void draftQuery.refetch()}>
          Retry
        </Button>
      </Card>
    );
  }

  const profile = profileQuery.data ?? null;
  const draft = draftQuery.data ?? null;

  if (profile === null) {
    if (resumeId === null || draft === null) {
      return (
        <Card title="No profile yet">
          <p className="mb-3 text-sm text-gray-600 dark:text-gray-400">
            Upload a resume first — the AI draft becomes your editable profile.
          </p>
          <Link
            href="/"
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Go to upload
          </Link>
        </Card>
      );
    }
    return <ProfileFormShell profile={draft.draft_profile} highlightAi />;
  }

  if (resumeId !== null && draft !== null) {
    return (
      <MergeDiffPanel
        current={profile.structured_profile}
        draft={draft.draft_profile}
        isSaving={saveProfile.isPending}
        saveError={saveProfile.error?.message ?? null}
        savedRevisionSource={saveProfile.data?.last_revision?.source ?? null}
        onSave={(merged) =>
          saveProfile.mutate(
            { structured_profile: merged, source_resume_id: resumeId },
            {
              onSuccess: () => {
                void router.replace("/profile");
              },
            },
          )
        }
        onDiscard={() => void router.replace("/profile")}
      />
    );
  }

  return <ProfileFormShell profile={profile.structured_profile} highlightAi={false} />;
}
