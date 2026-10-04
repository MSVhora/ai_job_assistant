"use client";

import type { FieldErrors, UseFormRegister, UseFormSetValue } from "react-hook-form";

import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";

import { MAX_JD_CHARS, type CreateFormValues } from "./create-form-schema";
import { MatchSelect } from "./MatchSelect";
import { TailoringControl } from "./TailoringControl";

const MODES = [
  { value: "none", label: "No job description" },
  { value: "paste", label: "Paste one" },
  { value: "match", label: "From a match" },
] as const;

export function JdPicker({
  mode,
  profileId,
  matchId,
  errors,
  register,
  setValue,
}: {
  mode: CreateFormValues["jd_mode"];
  profileId: string;
  matchId: string;
  errors: FieldErrors<CreateFormValues>;
  register: UseFormRegister<CreateFormValues>;
  setValue: UseFormSetValue<CreateFormValues>;
}) {
  return (
    <div className="flex flex-col gap-3">
      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-sm font-medium text-gray-700">Tailor to a job</legend>
        <div className="flex flex-wrap gap-2">
          {MODES.map((option) => (
            <label
              key={option.value}
              className="cursor-pointer rounded-full border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 has-[:checked]:border-violet-500 has-[:checked]:bg-violet-50 has-[:checked]:font-semibold has-[:checked]:text-violet-800 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-violet-600"
            >
              <input
                type="radio"
                value={option.value}
                className="sr-only"
                {...register("jd_mode")}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      {mode === "paste" && (
        <Field
          label="Job description"
          htmlFor="resume-jd"
          error={errors.job_description?.message}
          hint={`Up to ${MAX_JD_CHARS.toLocaleString("en-US")} characters. It is treated as data, never as instructions.`}
        >
          <Textarea
            id="resume-jd"
            rows={8}
            aria-invalid={errors.job_description !== undefined}
            {...register("job_description")}
          />
        </Field>
      )}
      {mode === "match" && (
        <MatchSelect
          profileId={profileId}
          value={matchId}
          error={errors.match_id?.message}
          onChange={(id) => {
            setValue("match_id", id, { shouldValidate: true });
          }}
        />
      )}
      {mode !== "none" && <TailoringControl register={register} />}
    </div>
  );
}
