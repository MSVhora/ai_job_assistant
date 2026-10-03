"use client";

import { useState } from "react";
import { Accordion } from "@/components/ui/accordion";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type {
  SourceFilterDecl,
  SourceInfo,
  StoredSearchQueries,
  StructuredProfile,
} from "@/lib/api";
import { useFormContext } from "react-hook-form";

import { SearchQueriesCard } from "./SearchQueriesCard";
import { SourceFiltersForm } from "./SourceFiltersForm";
import { POSTED_WITHIN_OPTIONS, type SearchFormValues } from "./search-form-schema";

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
          <Input id="job-country" {...form.register("country")} placeholder="in" maxLength={2} />
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
        <Field label="Results wanted" htmlFor="job-results" error={errors.results_wanted?.message}>
          <Input
            id="job-results"
            type="number"
            min={1}
            max={100}
            {...form.register("results_wanted")}
          />
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
      onToggle={() => {
        setOpen((previous) => !previous);
      }}
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
