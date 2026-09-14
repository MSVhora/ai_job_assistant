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
  query: QueryFieldValues;
  source: string;
  location: string;
  country: string;
  minSalary: string;
  maxSalary: string;
  posted_within: PostedWithinValue;
  results_wanted: number;
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

export function makeSearchFormSchema(source: SourceInfo | null) {
  const optionSchemas = new Map<string, z.ZodType>();
  for (const decl of source?.filters ?? []) {
    optionSchemas.set(decl.key, optionSchemaFor(decl));
  }
  return z.object({
    query: z
      .object({
        title: z.string().max(80, "Keep the title under 80 characters"),
        skills: z.string(),
        exclude: z.string(),
        options: z.record(z.string(), z.union([z.string(), z.boolean()])),
      })
      .superRefine((query, ctx) => {
        const keys = Object.keys(query.options);
        if (keys.length > MAX_OPTIONS) {
          ctx.addIssue({ code: "custom", path: ["options"], message: "Too many filters" });
          return;
        }
        for (const key of keys) {
          const schema = optionSchemas.get(key);
          if (!schema) {
            ctx.addIssue({
              code: "custom",
              path: ["options", key],
              message: "This source does not declare that filter",
            });
            continue;
          }
          const result = schema.safeParse(query.options[key]);
          if (!result.success) {
            ctx.addIssue({
              code: "custom",
              path: ["options", key],
              message: result.error.issues[0]?.message ?? "Invalid value",
            });
          }
        }
      }),
    source: z.string(),
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
    maxSalary: z
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
  });
}

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

type StoredQuerySpec = NonNullable<NonNullable<JobSearchRequest["source_queries"]>[string]>;
type StoredOptions = NonNullable<StoredQuerySpec["options"]>;

export function optionsFromStored(
  stored: StoredOptions | undefined,
  source: SourceInfo | null,
): OptionValues {
  if (!stored || source === null) return {};
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
  source: SourceInfo | null,
  profileCurrency: string | null,
  profileId: string | null,
): { payload: JobSearchRequest; missing: string[] } {
  const missing: string[] = [];
  if (profileId === null) {
    missing.push("profile");
  }
  if (values.source === "" || source === null) {
    missing.push("source");
  }
  const fields = values.query ?? emptyQueryFields();
  const title = fields.title.trim();
  const skills = splitList(fields.skills);
  const exclude = source?.supports_exclusions ? splitList(fields.exclude) : [];
  const options = source !== null ? coerceOptions(fields, source.filters ?? []) : {};
  const hasSpec = title !== "" || skills.length > 0 || Object.keys(options).length > 0;
  if (missing.length === 0 && !hasSpec) {
    missing.push(values.source);
  }

  const minSalary = values.minSalary.trim();
  const maxSalary = values.maxSalary.trim();
  const currency = profileCurrency && /^[A-Za-z]{3}$/.test(profileCurrency) ? profileCurrency : undefined;
  const spec = hasSpec
    ? {
        title: title || undefined,
        skills: skills.length > 0 ? skills : undefined,
        exclude: exclude.length > 0 ? exclude : undefined,
        options: Object.keys(options).length > 0 ? options : undefined,
      }
    : undefined;

  return {
    payload: {
      profile_id: profileId ?? undefined,
      source: values.source,
      country: values.country,
      location: values.location.trim() === "" ? null : values.location.trim(),
      results_wanted: values.results_wanted,
      max_days_old: values.posted_within === "any" ? undefined : Number(values.posted_within),
      source_queries: spec !== undefined ? { [values.source]: spec } : undefined,
      salary_min: minSalary === "" ? undefined : Number(minSalary),
      salary_max: maxSalary === "" ? undefined : Number(maxSalary),
      salary_currency: currency,
    },
    missing,
  };
}
