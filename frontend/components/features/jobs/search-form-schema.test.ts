import { describe, expect, it } from "vitest";

import type { SourceInfo } from "@/lib/api";

import {
  emptyQueryFields,
  makeSearchFormSchema,
  optionsFromStored,
  toSearchRequest,
  type SearchFormValues,
} from "./search-form-schema";

function source(overrides: Partial<SourceInfo>): SourceInfo {
  return {
    name: "adzuna",
    is_official_api: true,
    disclosure_required: false,
    is_configured: true,
    enabled: true,
    supports_exclusions: true,
    ...overrides,
  };
}

const adzunaFilters = [
  {
    key: "title_only",
    label: "Title-only search",
    type: "boolean" as const,
    required: false,
    help_text: "Match the title phrase only",
  },
  {
    key: "distance_km",
    label: "Radius (km)",
    type: "number" as const,
    required: false,
    placeholder: "25",
  },
  {
    key: "sort_by",
    label: "Sort by",
    type: "select" as const,
    required: false,
    options: [
      { value: "relevance", label: "Relevance" },
      { value: "date", label: "Date posted" },
    ],
  },
];

const linkedinFilters = [
  {
    key: "workplace_type",
    label: "Workplace type",
    type: "select" as const,
    required: false,
    options: [
      { value: "remote", label: "Remote" },
      { value: "hybrid", label: "Hybrid" },
    ],
  },
  {
    key: "company_ids",
    label: "Company IDs",
    type: "multiselect" as const,
    required: false,
    help_text: "LinkedIn company IDs to target",
  },
];

const adzuna = source({ name: "adzuna", filters: adzunaFilters });
const linkedin = source({
  name: "apify_linkedin",
  is_official_api: false,
  supports_exclusions: false,
  filters: linkedinFilters,
});

function baseValues(sourceInfo: SourceInfo): SearchFormValues {
  return {
    query: emptyQueryFields(),
    source: sourceInfo.name,
    location: "",
    country: "in",
    minSalary: "",
    maxSalary: "",
    posted_within: "any",
    results_wanted: 10,
  };
}

describe("makeSearchFormSchema", () => {
  it("accepts valid declared options", () => {
    const schema = makeSearchFormSchema(adzuna);
    const result = schema.safeParse({
      ...baseValues(adzuna),
      query: {
        title: "Engineer",
        skills: "",
        exclude: "",
        options: { title_only: true, distance_km: "25", sort_by: "date" },
      },
    });
    expect(result.success).toBe(true);
  });

  it("rejects an undeclared option key", () => {
    const schema = makeSearchFormSchema(adzuna);
    const result = schema.safeParse({
      ...baseValues(adzuna),
      query: {
        title: "Engineer",
        skills: "",
        exclude: "",
        options: { nonexistent: "x" },
      },
    });
    expect(result.success).toBe(false);
    expect(JSON.stringify(result.error?.issues)).toContain("does not declare");
  });

  it("rejects an undeclared select value", () => {
    const schema = makeSearchFormSchema(adzuna);
    const result = schema.safeParse({
      ...baseValues(adzuna),
      query: {
        title: "Engineer",
        skills: "",
        exclude: "",
        options: { sort_by: "salary" },
      },
    });
    expect(result.success).toBe(false);
    expect(JSON.stringify(result.error?.issues)).toContain("listed values");
  });

  it("rejects a non-integer number", () => {
    const schema = makeSearchFormSchema(adzuna);
    const result = schema.safeParse({
      ...baseValues(adzuna),
      query: { title: "", skills: "", exclude: "", options: { distance_km: "2.5" } },
    });
    expect(result.success).toBe(false);
    expect(JSON.stringify(result.error?.issues)).toContain("whole number");
  });

  it("accepts any options before a source is picked", () => {
    const schema = makeSearchFormSchema(null);
    const result = schema.safeParse(baseValues(adzuna));
    expect(result.success).toBe(true);
  });
});

describe("toSearchRequest", () => {
  it("builds a single-source payload with native option types", () => {
    const values = baseValues(adzuna);
    values.query = {
      title: "Engineer",
      skills: "",
      exclude: "intern",
      options: {
        title_only: true,
        distance_km: "25",
        sort_by: "",
      },
    };
    const { payload, missing } = toSearchRequest(values, adzuna, "INR", "p-1");
    expect(missing).toEqual([]);
    expect(payload.source).toBe("adzuna");
    expect(payload.source_queries?.adzuna).toMatchObject({
      title: "Engineer",
      options: { title_only: true, distance_km: 25 },
    });
    expect(Object.keys(payload.source_queries?.adzuna?.options ?? {})).not.toContain("sort_by");
    expect(payload.salary_currency).toBe("INR");
  });

  it("reports missing source and empty spec", () => {
    const values = baseValues(adzuna);
    const { missing } = toSearchRequest(values, adzuna, null, "p-1");
    expect(missing).toEqual(["adzuna"]);
    const noSource = baseValues(adzuna);
    const { missing: sourceMissing, payload } = toSearchRequest(noSource, null, null, "p-1");
    expect(sourceMissing).toEqual(["source"]);
    expect(payload.source_queries).toBeUndefined();
  });

  it("omits exclusion for sources without support and omits unset salary max", () => {
    const values = baseValues(linkedin);
    values.query = {
      title: "Engineer",
      skills: "",
      exclude: "interns",
      options: { workplace_type: "hybrid", company_ids: "123, 456" },
    };
    const { payload, missing } = toSearchRequest(values, linkedin, null, "p-1");
    expect(missing).toEqual([]);
    const spec = payload.source_queries?.apify_linkedin;
    expect(spec?.exclude).toBeUndefined();
    expect(spec?.options).toMatchObject({
      company_ids: ["123", "456"],
      workplace_type: "hybrid",
    });
    expect(payload.salary_max).toBeUndefined();
    expect(payload.salary_min).toBeUndefined();
  });

  it("sends min and max salary", () => {
    const values = baseValues(adzuna);
    values.minSalary = "100";
    values.maxSalary = "200";
    values.query.title = "Engineer";
    const { payload } = toSearchRequest(values, adzuna, null, "p-1");
    expect(payload.salary_min).toBe(100);
    expect(payload.salary_max).toBe(200);
  });
});

describe("optionsFromStored", () => {
  it("converts stored native types to form values", () => {
    const options = optionsFromStored(
      { title_only: true, distance_km: 25, sort_by: "date" },
      adzuna,
    );
    expect(options).toEqual({
      title_only: true,
      distance_km: "25",
      sort_by: "date",
    });
  });

  it("renders multiselect lists as comma-separated strings", () => {
    const options = optionsFromStored({ company_ids: ["123", "456"] }, linkedin);
    expect(options).toEqual({ company_ids: "123, 456" });
  });

  it("ignores keys the source does not declare and handles missing stored options", () => {
    expect(optionsFromStored({ company_ids: ["1"] }, adzuna)).toEqual({});
    expect(optionsFromStored(undefined, adzuna)).toEqual({});
    expect(optionsFromStored({ title_only: true }, null)).toEqual({});
  });
});
