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
  CertificationsSection,
  EducationSection,
  AwardsSection,
  ExtraSectionsSection,
} from "./EducationCredentials";
import { ExperienceSection, ProjectsSection } from "./ExperienceProjects";
import {
  AiExtractedBadge,
  ContactIcon,
  DerivedFromExperienceBadge,
  HeadlineIcon,
  PreferencesIcon,
  SectionCard,
  SelectField,
  SkillsIcon,
  StringListField,
  TextField,
} from "./fields";
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
  const { register, control, formState, handleSubmit, watch } = useFormContext<ProfileFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: "contact.links" });
  const aiBadge = highlightAi ? <AiExtractedBadge /> : undefined;
  const seniorityIsDerived = watch("preferences.seniority_source") === "derived";
  const errors = formState.errors;

  const submit = handleSubmit((values) => {
    onSave(toProfilePayload(values));
  });

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <SectionCard
        title="Contact"
        description="How employers can reach you"
        icon={<ContactIcon />}
        badge={aiBadge}
        hasError={errors.contact !== undefined}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Full name"
            name="contact.full_name"
            placeholder="Jane Doe"
            error={errors.contact?.full_name?.message}
            badge={aiBadge}
          />
          <TextField
            label="Email"
            name="contact.email"
            type="email"
            placeholder="jane@example.com"
            error={errors.contact?.email?.message}
            badge={aiBadge}
          />
          <TextField label="Phone" name="contact.phone" placeholder="+1 555 000 0000" badge={aiBadge} />
          <TextField label="Location" name="contact.location" placeholder="Berlin, Germany" badge={aiBadge} />
          <TextField
            label="Country code"
            name="contact.country"
            placeholder="in"
            hint="ISO 3166-1 alpha-2, e.g. in."
            error={errors.contact?.country?.message}
            badge={aiBadge}
          />
        </div>
        <div className="mt-5">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-800">Links</span>
            <Button
              variant="secondary"
              className="rounded-full border-dashed px-4 py-1.5 text-xs font-semibold text-violet-700 hover:border-violet-400 hover:bg-violet-50"
              onClick={() => append(emptyLink)}
            >
              + Add link
            </Button>
          </div>
          {fields.length === 0 ? (
            <p className="rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-500">
              No links yet — add LinkedIn, GitHub, or a portfolio URL.
            </p>
          ) : (
            fields.map((field, index) => (
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
                  className="mt-7 rounded-full px-2.5 py-1.5 text-xs"
                  onClick={() => remove(index)}
                  aria-label={`Remove link ${index + 1}`}
                >
                  ✕
                </Button>
              </div>
            ))
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="Headline & summary"
        description="Your elevator pitch — what you do and what you're looking for"
        icon={<HeadlineIcon />}
        badge={aiBadge}
        hasError={errors.headline !== undefined || errors.summary !== undefined}
      >
        <div className="flex flex-col gap-4">
          <TextField
            label="Headline"
            name="headline"
            placeholder="Senior Android Developer"
            error={errors.headline?.message}
            badge={aiBadge}
          />
          <TextField
            label="Summary"
            name="summary"
            placeholder="A short paragraph summarising your experience and strengths…"
            badge={aiBadge}
          />
        </div>
      </SectionCard>

      <SectionCard
        title="Skills"
        description="Your strongest and most relevant skills — order matters"
        icon={<SkillsIcon />}
        badge={aiBadge}
        hasError={errors.skills !== undefined}
      >
        <StringListField
          control={control}
          name="skills"
          label="Skills"
          addLabel="Add skill"
          placeholder="e.g. Kotlin, React, SQL"
        />
      </SectionCard>

      <ExperienceSection />
      <ProjectsSection />
      <EducationSection />
      <CertificationsSection />
      <AwardsSection />
      <ExtraSectionsSection />

      <SectionCard
        title="Job preferences"
        description="Drives which jobs get matched and how they're ranked"
        icon={<PreferencesIcon />}
        badge={aiBadge}
        hasError={errors.preferences !== undefined}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Target title"
            name="preferences.target_title"
            placeholder="e.g. Senior Android Developer"
            badge={aiBadge}
          />
          <TextField
            label="Target location"
            name="preferences.target_location"
            placeholder="e.g. Berlin, Germany"
            badge={aiBadge}
          />
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
            badge={seniorityIsDerived ? <DerivedFromExperienceBadge /> : aiBadge}
            hint={
              seniorityIsDerived
                ? "Auto-filled from your experience dates. Pick a value to override it."
                : undefined
            }
          />
          <TextField
            label="Years of experience"
            name="years_of_experience"
            readOnly
            hint="Auto-estimated from your experience dates"
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
            placeholder="60000"
            error={errors.preferences?.salary_min?.message}
            badge={aiBadge}
          />
          <TextField
            label="Salary max"
            name="preferences.salary_max"
            placeholder="80000"
            error={errors.preferences?.salary_max?.message}
            badge={aiBadge}
          />
        </div>
      </SectionCard>

      <div className="sticky bottom-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-violet-100 bg-white/95 p-4 shadow-xl shadow-violet-100/60 backdrop-blur">
        <SaveStatus isSaving={isSaving} error={saveError} savedRevisionSource={savedRevisionSource} />
        {errors.root?.message && (
          <p role="alert" className="text-sm text-red-600">
            {errors.root.message}
          </p>
        )}
        <Button
          type="submit"
          disabled={isSaving}
          className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 py-2.5 font-semibold shadow-lg shadow-violet-200 hover:from-violet-700 hover:to-fuchsia-700"
        >
          {isSaving ? "Saving…" : "Save profile"}
        </Button>
      </div>
    </form>
  );
}
