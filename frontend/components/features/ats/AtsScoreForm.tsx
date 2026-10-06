"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { AtsLoadingView } from "@/components/features/ats/AtsLoadingView";
import { AtsReport } from "@/components/features/ats/AtsReport";
import { AtsSourceSelector } from "@/components/features/ats/AtsSourceSelector";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAtsScore } from "@/hooks/use-ats-score";

const MIN_JD_CHARS = 50;
const MAX_JD_CHARS = 15000;

const atsFormSchema = z
  .object({
    resume_id: z.string().uuid().nullish(),
    profile_id: z.string().uuid().nullish(),
    job_description: z
      .string()
      .trim()
      .min(MIN_JD_CHARS, `Add the full job description — at least ${MIN_JD_CHARS} characters.`)
      .max(MAX_JD_CHARS, `Job description is too long (max ${MAX_JD_CHARS} characters).`),
  })
  .refine((value) => Boolean(value.resume_id ?? value.profile_id), {
    path: ["job_description"],
    message: "Choose a resume or a saved profile first.",
  });

type AtsFormValues = z.infer<typeof atsFormSchema>;

export type AtsSourceMode = "resume" | "profile";

const PLACEHOLDER = "Paste the job description you want to score against — title, requirements, responsibilities and any listed qualifications.";

export function AtsScoreForm() {
  const score = useAtsScore();
  const [mode, setMode] = useState<AtsSourceMode>("resume");
  const [jobDescription, setJobDescription] = useState("");
  const {
    setValue,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AtsFormValues>({
    resolver: zodResolver(atsFormSchema),
    defaultValues: { resume_id: null, profile_id: null, job_description: "" },
  });

  const [uploadedName, setUploadedName] = useState<string | null>(null);

  const pickResume = (resumeId: string, filename: string) => {
    setValue("resume_id", resumeId, { shouldValidate: true });
    setValue("profile_id", null);
    setMode("resume");
    setUploadedName(filename);
  };

  const pickProfile = (profileId: string, label: string) => {
    setValue("profile_id", profileId, { shouldValidate: true });
    setValue("resume_id", null);
    setMode("profile");
    setUploadedName(label);
  };

  const onSubmit = (values: AtsFormValues) => {
    score.mutate({
      resume_id: values.resume_id ?? undefined,
      profile_id: values.profile_id ?? undefined,
      job_description: values.job_description,
    });
  };

  if (score.isPending) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <AtsLoadingView />
      </div>
    );
  }

  if (score.isSuccess) {
    return <AtsReport report={score.data} onReset={() => score.reset()} />;
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="flex w-full flex-col gap-5" noValidate>
      <AtsSourceSelector
        mode={mode}
        onModeChange={setMode}
        onResumePicked={pickResume}
        onProfilePicked={pickProfile}
        onSelectionCleared={() => {
          setValue("resume_id", null);
          setValue("profile_id", null);
          setUploadedName(null);
        }}
      />

      <div className="flex flex-col gap-1.5">
        <label htmlFor="ats-jd" className="text-sm font-semibold text-gray-900">
          Job description
        </label>
        <Textarea
          id="ats-jd"
          rows={9}
          placeholder={PLACEHOLDER}
          value={jobDescription}
          onChange={(event) => {
            setJobDescription(event.target.value);
            setValue("job_description", event.target.value, { shouldValidate: false });
          }}
          aria-invalid={Boolean(errors.job_description)}
          className="rounded-2xl border-violet-200 focus-visible:outline-violet-600"
        />
        <div className="flex items-center justify-between gap-3">
          <p role="alert" className="text-sm text-red-600">
            {errors.job_description?.message ?? ""}
          </p>
          <p className="text-xs text-gray-500" aria-live="polite">
            {jobDescription.length} / {MAX_JD_CHARS}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          disabled={isSubmitting || score.isPending}
          className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 py-2.5 font-semibold shadow-lg shadow-violet-200 hover:from-violet-700 hover:to-fuchsia-700"
        >
          Check ATS score
        </Button>
        <p aria-live="polite" className="text-sm text-gray-500">
          {uploadedName === null
            ? "Pick a resume or profile, then paste a job description."
            : `Scoring against: ${uploadedName}`}
        </p>
      </div>

      {score.isError && (
        <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {score.error.message} — try again in a moment.
        </div>
      )}
    </form>
    </div>
  );
}
