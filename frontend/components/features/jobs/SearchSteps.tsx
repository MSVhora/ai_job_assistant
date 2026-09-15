"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Accordion } from "@/components/ui/accordion";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type {
  ProfileSummary,
  SourceFilterDecl,
  SourceInfo,
  StoredSearchQueries,
  StructuredProfile,
} from "@/lib/api";
import { useFormContext, useWatch } from "react-hook-form";

import { ProfileSelector } from "./ProfileSelector";
import { SearchQueriesCard } from "./SearchQueriesCard";
import { SourceFiltersForm } from "./SourceFiltersForm";
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
  const decls = source.filters ?? [];
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
      {decls.length > 0 && <SourceFiltersAccordion decls={decls} />}
    </div>
  );
}

function SourceFiltersAccordion({ decls }: { decls: SourceFilterDecl[] }) {
  const [open, setOpen] = useState(false);
  return (
    <Accordion
      id="details-advanced-filters"
      open={open}
      onToggle={() => setOpen((previous) => !previous)}
      trigger={
        <span className="text-sm font-semibold text-gray-900">
          More filters for this source (optional)
        </span>
      }
    >
      {open && <SourceFiltersForm decls={decls} />}
    </Accordion>
  );
}

function optionDisplay(value: string | boolean | undefined, type: string): string | null {
  if (value === undefined) return null;
  if (type === "boolean") return value === true ? "On" : null;
  if (typeof value === "string" && value.trim() === "") return null;
  return String(value);
}

type ReviewRow = { label: string; value: string };

export function ReviewSummary({
  source,
  profileName,
  currency,
}: {
  source: SourceInfo;
  profileName: string | null;
  currency: string | null;
}) {
  const { control } = useFormContext<SearchFormValues>();
  const values = useWatch({ control });
  const query = values?.query ?? {};
  const title = query.title?.trim();
  const skills = query.skills?.trim();
  const exclude = source.supports_exclusions ? (query.exclude?.trim() ?? "") : null;
  const postedWithin =
    POSTED_WITHIN_OPTIONS.find((option) => option.value === values?.posted_within)?.label ?? "—";
  const advanced = (source.filters ?? [])
    .map((decl) => ({
      label: decl.label,
      display: optionDisplay((query.options ?? {})[decl.key], decl.type),
    }))
    .filter((entry): entry is { label: string; display: string } => entry.display !== null);

  const rows: ReviewRow[] = [
    { label: "Profile", value: profileName ?? "—" },
    { label: "Source", value: source.name },
    { label: "Search title", value: title === undefined || title === "" ? "—" : title },
    { label: "Include skills", value: skills === undefined || skills === "" ? "—" : skills },
    {
      label: "Exclude skills",
      value: exclude === null ? "not supported by this source" : exclude === "" ? "—" : exclude,
    },
    {
      label: "Location",
      value: (values?.location ?? "").trim() === "" ? "—" : (values?.location ?? "").trim(),
    },
    {
      label: "Country",
      value: (values?.country ?? "").trim() === "" ? "—" : (values?.country ?? "").trim(),
    },
    { label: "Posted within", value: postedWithin },
    {
      label: "Min. salary",
      value:
        (values?.minSalary ?? "").trim() === ""
          ? "—"
          : `${values.minSalary}${currency !== null ? ` ${currency}` : ""}`,
    },
    {
      label: "Max. salary",
      value: (values?.maxSalary ?? "").trim() === "" ? "—" : `${values.maxSalary}${currency !== null ? ` ${currency}` : ""}`,
    },
    { label: "Results wanted", value: String(values?.results_wanted ?? "—") },
    {
      label: "Advanced filters",
      value:
        advanced.length === 0
          ? "none"
          : advanced.map((entry) => `${entry.label}: ${entry.display}`).join(", "),
    },
  ];

  return (
    <section aria-label="Review of the search you are about to start">
      <h3 className="text-sm font-bold tracking-tight text-gray-900">Review</h3>
      <dl className="mt-2 flex flex-col rounded-2xl border border-violet-100 bg-violet-50/50 p-3.5">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between gap-4 border-b border-violet-100/70 py-1.5 text-sm last:border-0 last:pb-0"
          >
            <dt className="shrink-0 text-xs font-semibold uppercase tracking-wide text-gray-500">
              {row.label}
            </dt>
            <dd className="min-w-0 break-words text-right text-gray-900">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
