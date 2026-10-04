"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Card } from "@/components/ui/card";
import { useProfiles } from "@/hooks/use-profiles";

import { ResumeCreateForm } from "./ResumeCreateForm";
import { ResumeDocumentList } from "./ResumeDocumentList";

export function ResumeBuilderPageClient() {
  const params = useSearchParams();
  const profiles = useProfiles();
  const requestedProfile = params.get("profile");
  const matchId = params.get("match");

  if (profiles.isPending) {
    return <div className="h-48 animate-pulse rounded-3xl bg-white/70" aria-busy="true" />;
  }
  if (profiles.isError) {
    return (
      <div
        role="alert"
        className="rounded-3xl border border-red-200 bg-red-50 p-5 text-sm text-red-800"
      >
        Could not load your profiles from the backend. Make sure the API is running.
        <button
          type="button"
          onClick={() => void profiles.refetch()}
          className="ml-3 rounded-full border border-red-300 px-3 py-1 text-xs font-semibold hover:bg-red-100"
        >
          Retry
        </button>
      </div>
    );
  }
  const known = profiles.data.find((profile) => profile.profile_id === requestedProfile);
  const initialProfileId = known?.profile_id ?? profiles.data[0]?.profile_id ?? "";

  return (
    <div className="flex flex-col gap-5">
      {profiles.data.length === 0 ? (
        <Card>
          <p className="text-sm text-gray-700">
            A resume is built from a profile.{" "}
            <Link
              href="/upload"
              className="font-semibold text-violet-700 underline underline-offset-2"
            >
              Upload a resume to create one
            </Link>
            .
          </p>
        </Card>
      ) : (
        <ResumeCreateForm
          key={`${initialProfileId}:${matchId ?? ""}`}
          profiles={profiles.data}
          initialProfileId={initialProfileId}
          initialMatchId={matchId}
        />
      )}
      <ResumeDocumentList />
    </div>
  );
}
