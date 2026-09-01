"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  toProfilePayload,
  type ProfileFormValues,
} from "@/lib/profile-schema";
import type { StructuredProfile } from "@/lib/api";

import {
  EducationSection,
  CertificationsSection,
  AwardsSection,
  ExtraSectionsSection,
} from "./EducationCredentials";
import { ExperienceSection, ProjectsSection } from "./ExperienceProjects";
import { AiExtractedBadge, SectionCard, SelectField, StringListField, TextField } from "./fields";
import { SaveStatus } from "./SaveStatus";

const emptyLink = { label: "", url: "" };

const REMOTE_OPTIONS = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
  { value: "flexible", label: "Flexible" },
] as const;

const SENIORITY_OPTIONS = [
  { value: "intern", label: "Intern" },
  { value: "junior", label: "Junior" },
  { value: "mid", label: "Mid-level" },
  { value: "senior", label: "Senior" },
  { value: "staff", label: "Staff" },
  { value: "lead", label: "Lead" },
  { value: "principal", label: "Principal" },
  { value: "manager", label: "Manager" },
  { value: "director", label: "Director" },
  { value: "executive", label: "Executive" },
] as const;

export function ProfileReviewForm({
  highlightAi,
  isSaving,
  saveError,
  savedRevisionSource,
  onSave,
}: {
  highlightAi: boolean;
  isSaving: boolean;
  saveError: string | null;
  savedRevisionSource: string | null;
  onSave: (profile: StructuredProfile) => void;
}) {
  const { register, control, formState, handleSubmit } = useFormContext<ProfileFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: "contact.links" });
  const aiBadge = highlightAi ? <AiExtractedBadge /> : undefined;
  const errors = formState.errors;

  const submit = handleSubmit((values) => {
    onSave(toProfilePayload(values));
  });

  return (
    <form onSubmit={submit} className="flex flex-col gap-6" noValidate>
      <SectionCard title="Contact" badge={aiBadge}>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Full name"
            name="contact.full_name"
            error={errors.contact?.full_name?.message}
            badge={aiBadge}
          />
          <TextField label="Email" name="contact.email" error={errors.contact?.email?.message} badge={aiBadge} />
          <TextField label="Phone" name="contact.phone" badge={aiBadge} />
          <TextField label="Location" name="contact.location" badge={aiBadge} />
        </div>
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-800 dark:text-gray-200">Links</span>
            <Button variant="secondary" onClick={() => append(emptyLink)}>
              Add link
            </Button>
          </div>
          {fields.map((field, index) => (
            <div key={field.id} className="mb-2 grid grid-cols-[1fr_2fr_auto] items-start gap-2">
              <Field label="Label" htmlFor={`contact.links.${index}.label`}>
                <Input
                  id={`contact.links.${index}.label`}
                  {...register(`contact.links.${index}.label`)}
                  placeholder="LinkedIn"
                />
              </Field>
              <Field
                label="URL"
                htmlFor={`contact.links.${index}.url`}
                error={errors.contact?.links?.[index]?.url?.message}
              >
                <Input
                  id={`contact.links.${index}.url`}
                  {...register(`contact.links.${index}.url`)}
                  placeholder="https://…"
                />
              </Field>
              <Button
                variant="danger"
                className="mt-7 px-2 py-1"
                onClick={() => remove(index)}
                aria-label={`Remove link ${index + 1}`}
              >
                ✕
              </Button>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Headline & summary" badge={aiBadge}>
        <div className="flex flex-col gap-4">
          <TextField label="Headline" name="headline" error={errors.headline?.message} badge={aiBadge} />
          <TextField label="Summary" name="summary" badge={aiBadge} />
        </div>
      </SectionCard>

      <SectionCard title="Skills" badge={aiBadge}>
        <StringListField control={control} name="skills" label="Skills" addLabel="Add skill" />
      </SectionCard>

      <ExperienceSection />
      <ProjectsSection />
      <EducationSection />
      <CertificationsSection />
      <AwardsSection />
      <ExtraSectionsSection />

      <SectionCard title="Job preferences" badge={aiBadge}>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="Target title" name="preferences.target_title" badge={aiBadge} />
          <TextField label="Target location" name="preferences.target_location" badge={aiBadge} />
          <SelectField
            label="Remote preference"
            name="preferences.remote_preference"
            options={REMOTE_OPTIONS}
            badge={aiBadge}
          />
          <SelectField
            label="Seniority"
            name="preferences.seniority"
            options={SENIORITY_OPTIONS}
            badge={aiBadge}
          />
          <TextField
            label="Work authorization"
            name="preferences.work_authorization"
            placeholder="e.g. EU citizen, H-1B needs sponsorship"
            badge={aiBadge}
          />
          <TextField label="Currency" name="preferences.currency" placeholder="EUR" badge={aiBadge} />
          <TextField
            label="Salary min"
            name="preferences.salary_min"
            error={errors.preferences?.salary_min?.message}
            badge={aiBadge}
          />
          <TextField
            label="Salary max"
            name="preferences.salary_max"
            error={errors.preferences?.salary_max?.message}
            badge={aiBadge}
          />
        </div>
      </SectionCard>

      <div className="sticky bottom-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white/95 p-4 shadow-md backdrop-blur dark:border-gray-800 dark:bg-gray-900/95">
        <SaveStatus isSaving={isSaving} error={saveError} savedRevisionSource={savedRevisionSource} />
        {errors.root?.message && (
          <p role="alert" className="text-sm text-red-600">
            {errors.root.message}
          </p>
        )}
        <Button type="submit" disabled={isSaving}>
          {isSaving ? "Saving…" : "Save profile"}
        </Button>
      </div>
    </form>
  );
}
