import { z } from "zod";

import type { JobSearchRequest, SourceInfo, StructuredProfile } from "@/lib/api";

export type QueryFieldValues = { title: string; skills: string; exclude: string };

export type SearchFormValues = {
  queries: Record<string, QueryFieldValues>;
  location: string;
  country: string;
  minSalary: string;
  results_wanted: number;
  sources: string[];
};

export const searchFormSchema = z.object({
  queries: z.record(
    z.string(),
    z.object({ title: z.string(), skills: z.string(), exclude: z.string() }),
  ),
  location: z.string().max(200, "Keep the location under 200 characters"),
  country: z
    .string()
    .trim()
    .toLowerCase()
    .regex(/^[a-z]{2}$/, "Two-letter country code, e.g. in"),
  minSalary: z
    .string()
    .refine((value) => value.trim() === "" || Number.isFinite(Number(value.trim())), {
      message: "Must be a number",
    }),
  results_wanted: z.coerce
    .number()
    .int("Whole number only")
    .min(1, "At least 1 result")
    .max(50, "Up to 50 results per search"),
  sources: z.array(z.string()).min(1, "Pick at least one source"),
});

export function emptyQueryFields(): QueryFieldValues {
  return { title: "", skills: "", exclude: "" };
}

export function splitList(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

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

export function seedSpec(profile: StructuredProfile): { title: string; skills: string[] } {
  const rawRole = profile.preferences?.target_title || profile.headline || "";
  const title = rawRole.split("|")[0].trim() || rawRole.trim();
  const picked: string[] = [];
  for (const skill of profile.skills) {
    if (picked.length >= MAX_SEED_SKILLS) break;
    const trimmed = skill.trim();
    if (!keywordLike(trimmed)) continue;
    const known = new Set(tokens([title, ...picked].join(" ")));
    if (tokens(trimmed).some((token) => known.has(token))) continue;
    picked.push(trimmed);
  }
  return { title, skills: picked };
}

export function supportsExclusions(sources: SourceInfo[], name: string): boolean {
  return sources.find((source) => source.name === name)?.supports_exclusions ?? false;
}

export function toSearchRequest(
  values: SearchFormValues,
  sources: SourceInfo[],
  profileCurrency: string | null,
): { payload: JobSearchRequest; missing: string[] } {
  const selected = values.sources;
  const sourceQueries: JobSearchRequest["source_queries"] = {};
  const missing: string[] = [];
  for (const name of selected) {
    const fields = values.queries[name] ?? emptyQueryFields();
    const title = fields.title.trim();
    const skills = splitList(fields.skills);
    if (title === "" && skills.length === 0) {
      missing.push(name);
      continue;
    }
    sourceQueries[name] = {
      title: title || undefined,
      skills: skills.length > 0 ? skills : undefined,
      exclude:
        supportsExclusions(sources, name) && splitList(fields.exclude).length > 0
          ? splitList(fields.exclude)
          : undefined,
    };
  }
  const minSalary = values.minSalary.trim();
  const currency = profileCurrency && /^[A-Za-z]{3}$/.test(profileCurrency) ? profileCurrency : undefined;
  return {
    payload: {
      country: values.country,
      location: values.location.trim() === "" ? null : values.location.trim(),
      results_wanted: values.results_wanted,
      sources: selected,
      source_queries: sourceQueries,
      salary_min: minSalary === "" ? undefined : Number(minSalary),
      salary_currency: currency,
    },
    missing,
  };
}
