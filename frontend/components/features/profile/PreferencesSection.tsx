"use client";

import { useFormContext } from "react-hook-form";
import type { ReactNode } from "react";

import type { ProfileFormValues } from "@/lib/profile-schema";

import { SectionCard } from "./cards";
import { DerivedFromExperienceBadge, SelectField, TextField } from "./fields";
import { PreferencesIcon } from "./profile-icons";

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

export function PreferencesSection({ aiBadge }: { aiBadge: ReactNode }) {
  const { formState, watch } = useFormContext<ProfileFormValues>();
  const seniorityIsDerived = watch("preferences.seniority_source") === "derived";
  const errors = formState.errors;

  return (
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
  );
}
