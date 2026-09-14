import { z } from "zod";

import type { JobSearchRequest, SourceFilterDecl, SourceInfo, StructuredProfile } from "@/lib/api";

export type OptionValues = Record<string, string | boolean>;

export type QueryFieldValues = {
  title: string;
  skills: string;
  exclude: string;
  options: OptionValues;
};

export type PostedWithinValue = "any" | "1" | "7" | "30";

export type SearchFormValues = {
  queries: Record<string, QueryFieldValues>;
  location: string;
  country: string;
  minSalary: string;
  posted_within: PostedWithinValue;
  results_wanted: number;
  sources: string[];
};

export const POSTED_WITHIN_OPTIONS: { value: PostedWithinValue; label: string }[] = [
  { value: "any", label: "Any time" },
  { value: "1", label: "Last 24 hours" },
  { value: "7", label: "Last week" },
  { value: "30", label: "Last month" },
];

const MAX_OPTIONS = 12;
const MAX_OPTION_VALUE_LENGTH = 200;

function optionSchemaFor(decl: SourceFilterDecl): z.ZodType {
  switch (decl.type) {
    case "number":
      return z
        .string()
        .refine(
          (value) =>
            value.trim() === "" || (Number.isInteger(Number(value)) && Number(value) >= 0),
          { message: "Must be a whole number" },
        );
    case "select": {
      const allowed = (decl.options ?? []).map((option) => option.value);
      return z
        .string()
        .refine((value) => value === "" || allowed.includes(value), {
          message: "Pick one of the listed values",
        });
    }
    case "boolean":
      return z.boolean();
    case "multiselect":
      return z.string().max(MAX_OPTION_VALUE_LENGTH, "Keep the list under 200 characters");
    default:
      return z.string().max(MAX_OPTION_VALUE_LENGTH, "Keep it under 200 characters");
  }
}

export function makeSearchFormSchema(sources: SourceInfo[]) {
  const optionSchemas = new Map<string, Record<string, z.ZodType>>();
  for (const source of sources) {
    const fields: Record<string, z.ZodType> = {};
    for (const decl of source.filters ?? []) {
      fields[decl.key] = optionSchemaFor(decl);
    }
    optionSchemas.set(source.name, fields);
  }
  return z.object({
    queries: z
      .record(
        z.string(),
        z.object({
          title: z.string(),
          skills: z.string(),
          exclude: z.string(),
          options: z.record(z.string(), z.union([z.string(), z.boolean()])),
        }),
      )
      .superRefine((queries, ctx) => {
        for (const [name, query] of Object.entries(queries)) {
          const schemas = optionSchemas.get(name) ?? {};
          const keys = Object.keys(query.options);
          if (keys.length > MAX_OPTIONS) {
            ctx.addIssue({ code: "custom", path: [name, "options"], message: "Too many filters" });
            continue;
          }
          for (const key of keys) {
            const schema = schemas[key];
            if (!schema) {
              ctx.addIssue({
                code: "custom",
                path: [name, "options", key],
                message: "This source does not declare that filter",
              });
              continue;
            }
            const result = schema.safeParse(query.options[key]);
            if (!result.success) {
              ctx.addIssue({
                code: "custom",
                path: [name, "options", key],
                message: result.error.issues[0]?.message ?? "Invalid value",
              });
            }
          }
        }
      }),
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
    posted_within: z.enum(["any", "1", "7", "30"]),
    results_wanted: z.coerce
      .number()
      .int("Whole number only")
      .min(1, "At least 1 result")
      .max(50, "Up to 50 results per search"),
    sources: z.array(z.string()).min(1, "Pick at least one source"),
  });
}

export const searchFormSchema = makeSearchFormSchema([]);

export function emptyQueryFields(): QueryFieldValues {
  return { title: "", skills: "", exclude: "", options: {} };
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

export function declaredFilters(sources: SourceInfo[], name: string): SourceFilterDecl[] {
  return sources.find((source) => source.name === name)?.filters ?? [];
}

type StoredQuerySpec = NonNullable<NonNullable<JobSearchRequest["source_queries"]>[string]>;
type StoredOptions = NonNullable<StoredQuerySpec["options"]>;

export function optionsFromStored(
  stored: StoredOptions | undefined,
  source: SourceInfo,
): OptionValues {
  if (!stored) return {};
  const options: OptionValues = {};
  for (const decl of source.filters ?? []) {
    const value = stored[decl.key];
    if (value === undefined) continue;
    if (decl.type === "boolean") {
      options[decl.key] = value === true;
    } else if (Array.isArray(value)) {
      options[decl.key] = value.join(", ");
    } else if (typeof value === "string" || typeof value === "number") {
      options[decl.key] = String(value);
    }
  }
  return options;
}

function coerceOptions(
  fields: QueryFieldValues,
  decls: SourceFilterDecl[],
): StoredOptions {
  const options: StoredOptions = {};
  for (const decl of decls) {
    const raw = fields.options[decl.key];
    if (raw === undefined) continue;
    if (decl.type === "boolean") {
      if (raw === true) options[decl.key] = true;
      continue;
    }
    if (typeof raw !== "string") continue;
    const value = raw.trim();
    if (value === "") continue;
    if (decl.type === "number") {
      const parsed = Number(value);
      if (Number.isInteger(parsed) && parsed >= 0) options[decl.key] = parsed;
      continue;
    }
    if (decl.type === "multiselect") {
      const list = splitList(value);
      if (list.length > 0) options[decl.key] = list;
      continue;
    }
    options[decl.key] = value;
  }
  return options;
}

export function toSearchRequest(
  values: SearchFormValues,
  sources: SourceInfo[],
  profileCurrency: string | null,
  profileId: string | null,
): { payload: JobSearchRequest; missing: string[] } {
  const selected = values.sources;
  const sourceQueries: JobSearchRequest["source_queries"] = {};
  const missing: string[] = [];
  if (profileId === null) {
    missing.push("profile");
  }
  for (const name of selected) {
    const fields = values.queries[name] ?? emptyQueryFields();
    const title = fields.title.trim();
    const skills = splitList(fields.skills);
    const options = coerceOptions(fields, declaredFilters(sources, name));
    if (title === "" && skills.length === 0 && Object.keys(options).length === 0) {
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
      options: Object.keys(options).length > 0 ? options : undefined,
    };
  }
  const minSalary = values.minSalary.trim();
  const currency = profileCurrency && /^[A-Za-z]{3}$/.test(profileCurrency) ? profileCurrency : undefined;
  return {
    payload: {
      profile_id: profileId ?? undefined,
      country: values.country,
      location: values.location.trim() === "" ? null : values.location.trim(),
    results_wanted: values.results_wanted,
    max_days_old:
      values.posted_within === "any" ? undefined : Number(values.posted_within),
    sources: selected,
      source_queries: sourceQueries,
      salary_min: minSalary === "" ? undefined : Number(minSalary),
      salary_currency: currency,
    },
    missing,
  };
}
