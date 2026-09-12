"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useCreateProfile } from "@/hooks/use-profiles";
import {
  profileFormSchema,
  toFormValues,
  type ProfileFormValues,
} from "@/lib/profile-schema";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import type { DraftProfileResponse, StructuredProfile } from "@/lib/api";

import { ProfileReviewForm } from "./ProfileReviewForm";

export function FirstReview({ draft }: { draft: DraftProfileResponse }) {
  const router = useRouter();
  const createProfile = useCreateProfile();
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const form = useForm<ProfileFormValues>({
    resolver: standardSchemaResolver(profileFormSchema),
    defaultValues: toFormValues(draft.draft_profile),
    mode: "onBlur",
  });

  const save = (structuredProfile: StructuredProfile) => {
    if (name.trim() === "") {
      setNameError("Give this profile a name (e.g. Senior Android Developer)");
      return;
    }
    setNameError(null);
    createProfile.mutate(
      {
        name: name.trim(),
        structured_profile: structuredProfile,
        source_resume_id: draft.resume_id,
      },
      {
        onSuccess: (created) => {
          void router.replace(`/profile?profile=${created.profile_id}`);
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <section
        aria-labelledby="profile-name-heading"
        className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur"
      >
        <h2 id="profile-name-heading" className="text-lg font-bold tracking-tight text-gray-900">
          Name this profile
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          One career can seed several profiles — e.g. a native-Android track and a broader SWE track.
        </p>
        <div className="mt-4">
          <Field
            label="Profile name"
            htmlFor="profile-name"
            error={nameError ?? undefined}
          >
            <Input
              id="profile-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Senior Android Developer"
              aria-invalid={nameError ? true : undefined}
            />
          </Field>
        </div>
      </section>
      <FormProvider {...form}>
        <ProfileReviewForm
          highlightAi
          isSaving={createProfile.isPending}
          saveError={createProfile.error?.message ?? null}
          savedRevisionSource={createProfile.data?.last_revision?.source ?? null}
          onSave={save}
        />
      </FormProvider>
      <p className="text-center text-xs text-gray-500">
        Saving creates a new profile — the resume and its draft stay untouched.
      </p>
    </div>
  );
}
