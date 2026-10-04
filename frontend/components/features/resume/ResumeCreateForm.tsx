"use client";

import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { useRouter } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { useCreateResumeDocument } from "@/hooks/use-resume-documents";
import type { ProfileSummary } from "@/lib/api";

import {
  LENGTH_OPTIONS,
  TEMPLATE_OPTIONS,
  createFormSchema,
  defaultCreateValues,
  toCreatePayload,
  type CreateFormValues,
} from "./create-form-schema";
import { JdPicker } from "./JdPicker";

export function ResumeCreateForm({
  profiles,
  initialProfileId,
  initialMatchId,
}: {
  profiles: ProfileSummary[];
  initialProfileId: string;
  initialMatchId: string | null;
}) {
  const router = useRouter();
  const create = useCreateResumeDocument();
  const {
    register,
    handleSubmit,
    setValue,
    control,
    formState: { errors },
  } = useForm<CreateFormValues>({
    resolver: standardSchemaResolver(createFormSchema),
    defaultValues: defaultCreateValues(initialProfileId, initialMatchId),
  });
  const [mode, profileId, matchId] = useWatch({
    control,
    name: ["jd_mode", "profile_id", "match_id"],
  });

  const onSubmit = handleSubmit((values) => {
    create.mutate(toCreatePayload(values), {
      onSuccess: (document) => {
        router.push(`/resume-builder/${document.id}`);
      },
    });
  });

  return (
    <Card title={<h2 className="text-lg font-semibold text-gray-900">New resume</h2>}>
      <form onSubmit={(event) => void onSubmit(event)} className="flex flex-col gap-4" noValidate>
        <Field label="Profile" htmlFor="resume-profile" error={errors.profile_id?.message}>
          <Select
            id="resume-profile"
            aria-invalid={errors.profile_id !== undefined}
            {...register("profile_id")}
          >
            <option value="">Choose a profile</option>
            {profiles.map((profile) => (
              <option key={profile.profile_id} value={profile.profile_id}>
                {profile.name}
              </option>
            ))}
          </Select>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Length"
            htmlFor="resume-length"
            hint="The most pages it may take — pages need not be full."
          >
            <Select id="resume-length" {...register("page_target")}>
              {LENGTH_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Template" htmlFor="resume-template">
            <Select id="resume-template" {...register("template")}>
              {TEMPLATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <JdPicker
          mode={mode}
          profileId={profileId}
          matchId={matchId}
          errors={errors}
          register={register}
          setValue={setValue}
        />
        <Checkbox
          label="Exclude bullets derived from private repositories"
          {...register("exclude_private")}
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Writing your resume…" : "Create resume"}
          </Button>
          <p aria-live="polite" className="text-xs text-gray-500">
            {create.isPending
              ? "Ranking your achievements and writing bullets — this can take a minute. No PDF is made yet."
              : "You review the content first; a PDF is only made when you ask."}
          </p>
        </div>
        {create.isError && (
          <p role="alert" className="text-sm text-red-700">
            {create.error.message}
          </p>
        )}
      </form>
    </Card>
  );
}
