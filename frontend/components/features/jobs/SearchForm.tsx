"use client";

import { useEffect } from "react";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { useController, useForm } from "react-hook-form";
import { z } from "zod";

import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useProfile } from "@/hooks/use-profiles";
import { useStartJobSearch } from "@/hooks/use-job-search";
import type { JobSearchRequest, SourceInfo, StructuredProfile } from "@/lib/api";

import { SourceMultiSelect } from "./SourceMultiSelect";

const MAX_SEED_SKILLS = 2;

const TOKEN_SPLIT = /[^a-z0-9+#.]+/;

function keywordLike(skill: string): boolean {
  const trimmed = skill.trim();
  return (
    trimmed.length >= 2 &&
    trimmed.length <= 24 &&
    trimmed.split(/\s+/).length <= 3 &&
    !/[|&/]/.test(trimmed)
  );
}

function tokens(value: string): string[] {
  return value.toLowerCase().split(TOKEN_SPLIT).filter((token) => token !== "");
}

function buildSeed(profile: StructuredProfile): {
  query: string;
  location: string;
  country: string;
} {
  const rawRole = profile.preferences?.target_title || profile.headline || "";
  const role = rawRole.split("|")[0].trim() || rawRole.trim();
  const picked: string[] = [];
  for (const skill of profile.skills) {
    if (picked.length >= MAX_SEED_SKILLS) break;
    const trimmed = skill.trim();
    if (!keywordLike(trimmed)) continue;
    const known = new Set(tokens([role, ...picked].join(" ")));
    if (tokens(trimmed).some((token) => known.has(token))) continue;
    picked.push(trimmed);
  }
  return {
    query: [role, ...picked].filter((part) => part !== "").join(" "),
    location: profile.preferences?.target_location || profile.contact.location || "",
    country: profile.contact.country || "",
  };
}

const searchFormSchema = z.object({
  query: z
    .string()
    .trim()
    .min(1, "Describe what you are looking for")
    .max(200, "Keep the query under 200 characters"),
  location: z.string().max(200, "Keep the location under 200 characters"),
  country: z
    .string()
    .trim()
    .toLowerCase()
    .regex(/^[a-z]{2}$/, "Two-letter country code, e.g. de"),
  results_wanted: z.coerce
    .number()
    .int("Whole number only")
    .min(1, "At least 1 result")
    .max(50, "Up to 50 results per search"),
  sources: z.array(z.string()).min(1, "Pick at least one source"),
});

type SearchFormValues = z.infer<typeof searchFormSchema>;

export function SearchForm({
  sources,
  profileId,
  onStarted,
}: {
  sources: SourceInfo[];
  profileId: string | null;
  onStarted: (searchId: string) => void;
}) {
  const profile = useProfile(profileId);
  const start = useStartJobSearch();

  const seed = profile.data ? buildSeed(profile.data.structured_profile) : null;

  const form = useForm<SearchFormValues>({
    resolver: standardSchemaResolver(searchFormSchema),
    defaultValues: {
      query: "",
      location: "",
      country: "",
      results_wanted: 50,
      sources: sources.map((source) => source.name),
    },
    mode: "onBlur",
  });
  const sourcesField = useController({ control: form.control, name: "sources" });
  const selectedSources = (sourcesField.field.value as string[]) ?? [];

  useEffect(() => {
    if (seed !== null) {
      form.setValue("query", seed.query, { shouldValidate: false });
      form.setValue("location", seed.location, { shouldValidate: false });
      form.setValue("country", seed.country, { shouldValidate: false });
    }
    // Re-seed whenever the selected profile changes; never validate mid-seed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId, seed?.query, seed?.location, seed?.country]);

  const submit = form.handleSubmit((values) => {
    const payload: JobSearchRequest = {
      query: values.query,
      location: values.location.trim() === "" ? null : values.location.trim(),
      country: values.country,
      results_wanted: values.results_wanted,
      sources: values.sources,
    };
    start.mutate(payload, { onSuccess: (data) => onStarted(data.search_id) });
  });

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <Field
        label="Search query"
        htmlFor="job-query"
        error={form.formState.errors.query?.message}
        hint={
          profile.data
            ? `Seeded from profile "${profile.data.name}" (target title or headline + top matching skills) — edit freely.`
            : "Seeding needs a saved profile; enter a query manually or create one under Profile."
        }
      >
        <Input id="job-query" {...form.register("query")} placeholder="data analyst sql" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field
          label="Location (optional)"
          htmlFor="job-location"
          error={form.formState.errors.location?.message}
        >
          <Input id="job-location" {...form.register("location")} placeholder="Berlin" />
        </Field>
        <Field
          label="Country code"
          htmlFor="job-country"
          error={form.formState.errors.country?.message}
          hint="Two letters, e.g. de — required by the search API."
        >
          <Input
            id="job-country"
            {...form.register("country")}
            placeholder="de"
            maxLength={2}
            aria-invalid={form.formState.errors.country ? true : undefined}
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
      <SourceMultiSelect
        sources={sources}
        selected={selectedSources}
        onToggle={(name, checked) =>
          form.setValue(
            "sources",
            checked ? [...selectedSources, name] : selectedSources.filter((s) => s !== name),
            { shouldValidate: true },
          )
        }
        error={form.formState.errors.sources?.message}
      />
      <div>
        <button
          type="submit"
          disabled={start.isPending}
          className="rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          {start.isPending ? "Starting run…" : "Start search"}
        </button>
        {start.isError && (
          <p role="alert" className="mt-2 text-xs text-red-600 dark:text-red-400">
            {start.error.message}
          </p>
        )}
      </div>
    </form>
  );
}
