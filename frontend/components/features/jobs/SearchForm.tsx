"use client";

import { useEffect } from "react";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { FormProvider, useForm } from "react-hook-form";

import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SearchQueriesCard } from "@/components/features/jobs/SearchQueriesCard";
import { useProfile } from "@/hooks/use-profiles";
import { useStartJobSearch } from "@/hooks/use-job-search";
import type { SourceInfo } from "@/lib/api";

import {
  emptyQueryFields,
  searchFormSchema,
  seedSpec,
  toSearchRequest,
  type SearchFormValues,
} from "./search-form-schema";

export function SearchForm({
  sources,
  profileId,
  onStarted,
  selectedSources,
}: {
  sources: SourceInfo[];
  profileId: string | null;
  onStarted: (searchId: string) => void;
  selectedSources: string[];
}) {
  const profile = useProfile(profileId);
  const start = useStartJobSearch();
  const structured = profile.data?.structured_profile ?? null;
  const seed = structured !== null ? seedSpec(structured) : null;

  const form = useForm<SearchFormValues>({
    resolver: standardSchemaResolver(searchFormSchema),
    defaultValues: {
      queries: Object.fromEntries(
        sources.map((source) => [source.name, emptyQueryFields()]),
      ),
      location: "",
      country: "",
      minSalary: "",
      results_wanted: 50,
      sources: sources.map((source) => source.name),
    },
    mode: "onBlur",
  });

  useEffect(() => {
    form.setValue("sources", selectedSources, { shouldValidate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSources]);

  useEffect(() => {
    if (structured === null) return;
    const preferences = structured.preferences;
    form.setValue(
      "location",
      preferences?.target_location || structured.contact.location || "",
      {
        shouldValidate: false,
      },
    );
    form.setValue("country", structured.contact.country || "", {
      shouldValidate: false,
    });
    form.setValue(
      "minSalary",
      preferences?.salary_min !== undefined && preferences?.salary_min !== null
        ? String(preferences.salary_min)
        : "",
      { shouldValidate: false },
    );
    const queries: Record<
      string,
      { title: string; skills: string; exclude: string }
    > = {};
    for (const source of sources) {
      const stored = profile.data?.search_queries?.queries[source.name];
      const seeded = seed ?? { title: "", skills: [] };
      queries[source.name] = {
        title: stored?.title ?? seeded.title,
        skills: (stored?.skills ?? seeded.skills).join(", "),
        exclude: (stored?.exclude ?? []).join(", "),
      };
    }
    form.setValue("queries", queries, { shouldValidate: false });
    // Re-seed on profile switch and after a regenerate refreshes stored queries.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    profileId,
    profile.data?.updated_at,
    profile.data?.search_queries?.generated_at,
  ]);

  const submit = form.handleSubmit((values) => {
    const { payload, missing } = toSearchRequest(
      values,
      sources,
      structured?.preferences?.currency ?? null,
    );
    if (missing.length > 0) {
      form.setError("root", {
        message: `Add a title or skills for: ${missing.join(", ")}`,
      });
      return;
    }
    form.clearErrors("root");
    start.mutate(payload, { onSuccess: (data) => onStarted(data.search_id) });
  });

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <FormProvider {...form}>
        <SearchQueriesCard
          sources={sources.map((source) => ({
            name: source.name,
            is_official_api: source.is_official_api,
            supports_exclusions: source.supports_exclusions,
          }))}
          profileId={profileId}
          structuredProfile={structured}
          storedQueries={profile.data?.search_queries ?? null}
          updatedAt={profile.data?.updated_at}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Field
            label="Location (optional)"
            htmlFor="job-location"
            error={form.formState.errors.location?.message}
          >
            <Input
              id="job-location"
              {...form.register("location")}
              placeholder="Bangalore"
            />
          </Field>
          <Field
            label="Country code"
            htmlFor="job-country"
            error={form.formState.errors.country?.message}
            hint="Two letters, e.g. in."
          >
            <Input
              id="job-country"
              {...form.register("country")}
              placeholder="in"
              maxLength={2}
              aria-invalid={form.formState.errors.country ? true : undefined}
            />
          </Field>
          <Field
            label="Min. salary"
            htmlFor="job-min-salary"
            error={form.formState.errors.minSalary?.message}
            hint={
              structured?.preferences?.currency
                ? `Currency hint: ${structured.preferences.currency}.`
                : "Used as a filter where supported."
            }
          >
            <Input
              id="job-min-salary"
              type="number"
              min={0}
              {...form.register("minSalary")}
              placeholder="5000000"
            />
          </Field>
          <Field
            label="Results wanted"
            htmlFor="job-results"
            error={form.formState.errors.results_wanted?.message}
          >
            <Input
              id="job-results"
              type="number"
              min={1}
              max={50}
              {...form.register("results_wanted")}
            />
          </Field>
        </div>
      </FormProvider>
      <div className="flex shrink-0 flex-col gap-2 border-t border-gray-100 pt-3">
        <button
          type="submit"
          disabled={start.isPending}
          className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-200 transition-all hover:from-violet-700 hover:to-fuchsia-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          {start.isPending ? "Starting run…" : "Start AI search"}
        </button>
        {form.formState.errors.root && (
          <p role="alert" className="text-xs text-red-600">
            {form.formState.errors.root.message}
          </p>
        )}
        {start.isError && (
          <p role="alert" className="text-xs text-red-600">
            {start.error.message}
          </p>
        )}
      </div>
    </form>
  );
}
