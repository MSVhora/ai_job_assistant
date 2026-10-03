"use client";

import { useEffect } from "react";
import type { UseFormReturn } from "react-hook-form";

import type { ProfileResponse, SourceInfo, StructuredProfile } from "@/lib/api";

import { optionsFromStored, seedSpec, type SearchFormValues } from "./search-form-schema";

export function useSeedSearchForm({
  form,
  structured,
  profile,
  sourceName,
  selectedSource,
  activeProfileId,
}: {
  form: UseFormReturn<SearchFormValues>;
  structured: StructuredProfile | null;
  profile: ProfileResponse | undefined;
  sourceName: string;
  selectedSource: SourceInfo | null;
  activeProfileId: string | null;
}) {
  // Re-seed prefilled values on profile switch, source switch, and after a
  // regenerate refreshes the stored per-source queries.
  useEffect(() => {
    if (structured === null) {
      return;
    }
    const preferences = structured.preferences;
    const stored = profile?.search_queries?.queries[sourceName];
    const seeded = seedSpec(structured);
    form.reset({
      query: {
        title: stored?.title ?? seeded.title,
        skills_all: (stored?.skills_all ?? []).join(", "),
        skills: (stored?.skills ?? seeded.skills).join(", "),
        exclude: (stored?.exclude ?? []).join(", "),
        options: optionsFromStored(stored?.options, selectedSource),
      },
      source: sourceName,
      location: preferences?.target_location || structured.contact.location || "",
      country: structured.contact.country || "",
      minSalary:
        preferences?.salary_min !== undefined && preferences.salary_min !== null
          ? String(preferences.salary_min)
          : "",
      maxSalary:
        preferences?.salary_max !== undefined && preferences.salary_max !== null
          ? String(preferences.salary_max)
          : "",
      posted_within: "any" as const,
      results_wanted: 50,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProfileId, sourceName, profile?.updated_at, profile?.search_queries?.generated_at]);
}
