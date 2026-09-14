"use client";

import { Badge } from "@/components/ui/badge";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { ProfileSummary, SourceInfo, StoredSearchQueries, StructuredProfile } from "@/lib/api";
import { useFormContext, useWatch } from "react-hook-form";

import { ProfileSelector } from "./ProfileSelector";
import { SearchQueriesCard } from "./SearchQueriesCard";
import { POSTED_WITHIN_OPTIONS, type SearchFormValues } from "./search-form-schema";

export function ProfileStep({
  profiles,
  activeProfileId,
  profilesPending,
  profilesError,
  onSelectProfile,
}: {
  profiles: ProfileSummary[];
  activeProfileId: string | null;
  profilesPending: boolean;
  profilesError: boolean;
  onSelectProfile: (profileId: string) => void;
}) {
  return (
    <fieldset aria-label="Step 1: profile" className="flex flex-col gap-3">
      <ProfileSelector
        profiles={profiles}
        activeProfileId={activeProfileId}
        disabled={profilesPending || profilesError}
        onSelect={onSelectProfile}
        id="stepper-profile"
        hint="Every search run is scoped to exactly one profile."
      />
    </fieldset>
  );
}

export function SourceStep({
  sources,
  selectedSourceId,
  error,
  onSelect,
}: {
  sources: SourceInfo[];
  selectedSourceId: string;
  error?: string;
  onSelect: (sourceId: string) => void;
}) {
  return (
    <fieldset aria-label="Step 2: source" className="flex flex-col gap-2">
      <legend className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        Search one source
      </legend>
      {sources.map((source) => (
        <label
          key={source.name}
          className={`flex cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition-colors focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-violet-600 ${
            selectedSourceId === source.name
              ? "border-violet-500 bg-violet-50 font-semibold text-violet-800"
              : "border-gray-300 bg-white text-gray-700 hover:border-violet-300"
          } ${source.is_configured ? "" : "cursor-not-allowed opacity-60"}`}
        >
          <input
            type="radio"
            name="wizard-source"
            className="accent-violet-600"
            disabled={!source.is_configured}
            checked={selectedSourceId === source.name}
            onChange={() => onSelect(source.name)}
            aria-label={`Search ${source.name}`}
          />
          <span>{source.name}</span>
          <Badge variant={source.is_official_api ? "official-api" : "third-party-scraper"}>
            {source.is_official_api ? "Official API" : "Third-party scraper"}
          </Badge>
          {!source.is_configured && (
            <span className="text-xs text-amber-800">API key missing — set it in setup</span>
          )}
        </label>
      ))}
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </fieldset>
  );
}

export function DetailsStep({
  source,
  profileId,
  structuredProfile,
  storedQueries,
  updatedAt,
  currency,
}: {
  source: SourceInfo;
  profileId: string | null;
  structuredProfile: StructuredProfile | null;
  storedQueries: StoredSearchQueries | null | undefined;
  updatedAt: string | undefined;
  currency: string | null;
}) {
  const form = useFormContext<SearchFormValues>();
  const errors = form.formState.errors;
  return (
    <div aria-label="Step 3: search details" className="flex flex-col gap-4">
      <SearchQueriesCard
        source={source}
        profileId={profileId}
        structuredProfile={structuredProfile}
        storedQueries={storedQueries}
        updatedAt={updatedAt}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Location (optional)" htmlFor="job-location" error={errors.location?.message}>
          <Input id="job-location" {...form.register("location")} placeholder="Bangalore" />
        </Field>
        <Field
          label="Country code"
          htmlFor="job-country"
          error={errors.country?.message}
          hint="Two letters, e.g. in."
        >
          <Input
            id="job-country"
            {...form.register("country")}
            placeholder="in"
            maxLength={2}
          />
        </Field>
        <Field
          label="Min. salary"
          htmlFor="job-min-salary"
          error={errors.minSalary?.message}
          hint={currency ? `Currency hint: ${currency}.` : "Used as a filter where supported."}
        >
          <Input id="job-min-salary" type="number" min={0} {...form.register("minSalary")} />
        </Field>
        <Field
          label="Max. salary (optional)"
          htmlFor="job-max-salary"
          error={errors.maxSalary?.message}
          hint={currency ? `Currency hint: ${currency}.` : "Applied where the source supports it."}
        >
          <Input id="job-max-salary" type="number" min={0} {...form.register("maxSalary")} />
        </Field>
        <Field
          label="Results wanted"
          htmlFor="job-results"
          error={errors.results_wanted?.message}
        >
          <Input id="job-results" type="number" min={1} max={50} {...form.register("results_wanted")} />
        </Field>
        <Field
          label="Posted within"
          htmlFor="job-posted-within"
          hint="Applied at the source when supported (exact on Adzuna, closest bucket on LinkedIn)."
        >
          <Select id="job-posted-within" {...form.register("posted_within")}>
            {POSTED_WITHIN_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </div>
  );
}

export function reviewLine(
  values:
    | { query?: { title?: string; skills?: string } | undefined }
    | undefined,
  sourceName: string,
): string {
  const title = values?.query?.title?.trim() ?? "";
  const skills = values?.query?.skills?.trim() ?? "";
  const parts = [title, skills ? `skills ${skills}` : null].filter(
    (part): part is string => part !== null && part !== "",
  );
  return `${sourceName}: ${parts.length > 0 ? parts.join(" · ") : "no query yet"}`;
}

export function ReviewSummary({
  sourceName,
  profileName,
}: {
  sourceName: string;
  profileName: string | null;
}) {
  const { control } = useFormContext<SearchFormValues>();
  const values = useWatch({ control });
  const location = values?.location ?? "";
  const country = values?.country ?? "";
  return (
    <p className="rounded-xl bg-violet-50 px-3 py-2 text-xs text-violet-900">
      Review — {profileName ?? "no profile"} · {reviewLine(values, sourceName)}
      {location !== "" && ` · ${location}`}
      {` (${country})`}
    </p>
  );
}
