"use client";

import { useSearchParams } from "next/navigation";

import { ProfilesSection } from "@/components/features/ProfilesSection";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useProfiles } from "@/hooks/use-profiles";
import { useResumeDraft } from "@/hooks/use-resume-draft";

import { MergeMode } from "./MergeMode";
import { DraftErrorCard } from "./DraftErrorCard";
import { ProfileEditor } from "./ProfileEditor";
import { TargetChooser } from "./TargetChooser";

export function ProfilePageClient() {
  const searchParams = useSearchParams();
  const profileId = searchParams.get("profile");
  const resumeId = searchParams.get("resume");
  const profilesQuery = useProfiles();
  const draftQuery = useResumeDraft(resumeId);

  if (profileId !== null && resumeId !== null) {
    return <MergeMode profileId={profileId} resumeId={resumeId} />;
  }

  if (profileId !== null) {
    return <ProfileEditor profileId={profileId} />;
  }

  if (resumeId !== null) {
    if (profilesQuery.isPending || draftQuery.isPending) {
      return (
        <div className="h-96 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" aria-live="polite" />
      );
    }
    if (profilesQuery.isError) {
      return (
        <Card title="Could not load your profiles">
          <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
            {profilesQuery.error.message}
          </p>
          <Button variant="secondary" onClick={() => void profilesQuery.refetch()}>
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
    const profiles = profilesQuery.data;
    return <TargetChooser draft={draftQuery.data} profiles={profiles} />;
  }

  return <ProfilesSection />;
}
