"use client";

import Link from "next/link";
import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useProfile, useUpdateProfile } from "@/hooks/use-profiles";
import {
  profileFormSchema,
  toFormValues,
  type ProfileFormValues,
} from "@/lib/profile-schema";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import type { GapFillResponse, ProfileResponse } from "@/lib/api";

import { GapFillChat } from "./GapFillChat";
import { ProfileReviewForm } from "./ProfileReviewForm";

export function ProfileEditor({ profileId }: { profileId: string }) {
  const profileQuery = useProfile(profileId);

  if (profileQuery.isPending) {
    return (
      <div className="h-96 animate-pulse rounded-3xl bg-white/60" aria-live="polite" />
    );
  }

  if (profileQuery.isError) {
    return (
      <Card title="Could not load this profile">
        <p role="alert" className="mb-3 text-sm text-red-700">
          {profileQuery.error.message}
        </p>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => void profileQuery.refetch()}>
            Retry
          </Button>
          <Link href="/profile">
            <Button variant="secondary">Back to profiles</Button>
          </Link>
        </div>
      </Card>
    );
  }

  return <EditorBody profile={profileQuery.data} />;
}

export function EditorBody({ profile }: { profile: ProfileResponse }) {
  const updateProfile = useUpdateProfile();
  const renameProfile = useUpdateProfile();
  const [renaming, setRenaming] = useState(false);
  const [nameInput, setNameInput] = useState(profile.name);
  // Server-owned list of still-missing gap-fill fields; the chat section renders
  // only while it is non-empty and collapses the moment a turn completes.
  const [missingFields, setMissingFields] = useState<string[]>(profile.missing_fields ?? []);
  const form = useForm<ProfileFormValues>({
    resolver: standardSchemaResolver(profileFormSchema),
    defaultValues: toFormValues(profile.structured_profile),
    mode: "onBlur",
  });

  const applyGapFill = (data: GapFillResponse) => {
    setMissingFields(data.missing_fields.map((field) => field.key));
    const values = toFormValues(data.structured_profile);
    const touched = new Set(data.applied_fields.map((field) => field.field));
    const current = form.getValues();
    const next: ProfileFormValues = {
      ...current,
      contact: { ...current.contact },
      preferences: { ...current.preferences },
    };
    if (touched.has("contact.location")) {
      next.contact.location = values.contact.location;
    }
    if (touched.has("contact.country")) {
      next.contact.country = values.contact.country ?? "";
    }
    if (touched.has("preferences.target_location")) {
      next.preferences.target_location = values.preferences.target_location;
    }
    if (touched.has("preferences.remote_preference")) {
      next.preferences.remote_preference = values.preferences.remote_preference;
    }
    if (touched.has("preferences.salary_min")) {
      next.preferences.salary_min = values.preferences.salary_min;
    }
    if (touched.has("preferences.salary_max")) {
      next.preferences.salary_max = values.preferences.salary_max;
    }
    if (touched.has("preferences.currency")) {
      next.preferences.currency = values.preferences.currency;
    }
    if (touched.has("preferences.seniority")) {
      next.preferences.seniority = values.preferences.seniority;
    }
    if (touched.has("preferences.work_authorization")) {
      next.preferences.work_authorization = values.preferences.work_authorization;
    }
    form.reset(next);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur">
        {renaming ? (
          <div className="min-w-64 flex-1">
            <Field
              label="Profile name"
              htmlFor="rename-profile"
              error={renameProfile.error?.message}
            >
              <Input
                id="rename-profile"
                value={nameInput}
                onChange={(event) => setNameInput(event.target.value)}
              />
            </Field>
          </div>
        ) : (
          <div>
            <h2 className="text-xl font-bold tracking-tight text-gray-900">{profile.name}</h2>
            <p className="text-xs text-gray-500">
              {profile.source_resume_filename ? `From ${profile.source_resume_filename} · ` : ""}
              Updated {new Date(profile.updated_at).toLocaleString()}
            </p>
          </div>
        )}
        {renaming ? (
          <div className="flex gap-2">
            <Button
              disabled={renameProfile.isPending || nameInput.trim() === ""}
              onClick={() =>
                renameProfile.mutate(
                  { profileId: profile.profile_id, payload: { name: nameInput.trim() } },
                  {
                    onSuccess: () => {
                      setRenaming(false);
                    },
                  },
                )
              }
            >
              {renameProfile.isPending ? "Saving…" : "Save name"}
            </Button>
            <Button variant="secondary" onClick={() => setRenaming(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button
            variant="secondary"
            className="rounded-full px-4 py-1.5 text-xs"
            onClick={() => {
              setNameInput(profile.name);
              setRenaming(true);
            }}
          >
            Rename
          </Button>
        )}
      </div>

      {missingFields.length > 0 && (
        <GapFillChat profileId={profile.profile_id} onApplied={applyGapFill} />
      )}
      <FormProvider {...form}>
        <ProfileReviewForm
          highlightAi={false}
          isSaving={updateProfile.isPending}
          saveError={updateProfile.error?.message ?? null}
          savedRevisionSource={updateProfile.data?.last_revision?.source ?? null}
          onSave={(structuredProfile) =>
            updateProfile.mutate({
              profileId: profile.profile_id,
              payload: { structured_profile: structuredProfile },
            })
          }
        />
      </FormProvider>
      <Link href="/profile" className="text-center text-sm font-medium text-gray-600 underline underline-offset-2 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600">
        Back to all profiles
      </Link>
    </div>
  );
}
