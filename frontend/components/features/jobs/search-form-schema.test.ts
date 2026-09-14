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
    key: "date_posted",
    label: "Date posted",
    type: "select" as const,
    required: false,
    options: [
      { value: "anyTime", label: "Any time" },
      { value: "pastWeek", label: "Past week" },
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

function baseValues(sources: SourceInfo[]): SearchFormValues {
  return {
    queries: Object.fromEntries(sources.map((s) => [s.name, emptyQueryFields()])),
    location: "",
    country: "in",
    minSalary: "",
    posted_within: "any",
    results_wanted: 10,
    sources: sources.map((s) => s.name),
  };
}

describe("makeSearchFormSchema", () => {
  const sources = [
    source({ name: "adzuna", filters: adzunaFilters }),
    source({
      name: "apify_linkedin",
      is_official_api: false,
      supports_exclusions: false,
      filters: linkedinFilters,
    }),
  ];

  it("accepts valid declared options", () => {
    const schema = makeSearchFormSchema(sources);
    const result = schema.safeParse({
      ...baseValues(sources),
      queries: {
        adzuna: {
          title: "Engineer",
          skills: "",
          exclude: "",
          options: { title_only: true, distance_km: "25", sort_by: "date" },
        },
      },
    });
    expect(result.success).toBe(true);
  });

  it("rejects an undeclared option key", () => {
    const schema = makeSearchFormSchema(sources);
    const result = schema.safeParse({
      ...baseValues(sources),
      queries: {
        adzuna: {
          title: "Engineer",
          skills: "",
          exclude: "",
          options: { nonexistent: "x" },
        },
      },
    });
    expect(result.success).toBe(false);
    expect(JSON.stringify(result.error?.issues)).toContain("does not declare");
  });

  it("rejects an undeclared select value", () => {
    const schema = makeSearchFormSchema(sources);
    const result = schema.safeParse({
      ...baseValues(sources),
      queries: {
        adzuna: {
          title: "Engineer",
          skills: "",
          exclude: "",
          options: { sort_by: "salary" },
        },
      },
    });
    expect(result.success).toBe(false);
    expect(JSON.stringify(result.error?.issues)).toContain("listed values");
  });

  it("rejects a non-integer number", () => {
    const schema = makeSearchFormSchema(sources);
    const result = schema.safeParse({
      ...baseValues(sources),
      queries: {
        adzuna: { title: "", skills: "", exclude: "", options: { distance_km: "2.5" } },
      },
    });
    expect(result.success).toBe(false);
    expect(JSON.stringify(result.error?.issues)).toContain("whole number");
  });
});

describe("toSearchRequest options", () => {
  const sources = [
    source({ name: "adzuna", filters: adzunaFilters }),
    source({
      name: "apify_linkedin",
      is_official_api: false,
      supports_exclusions: false,
      filters: linkedinFilters,
    }),
  ];

  it("converts form values to native types and omits unset ones", () => {
    const values = baseValues(sources);
    values.queries.adzuna = {
      title: "Engineer",
      skills: "",
      exclude: "",
      options: {
        title_only: true,
        distance_km: "25",
        sort_by: "",
      },
    };
    values.queries.apify_linkedin = {
      title: "",
      skills: "",
      exclude: "",
      options: { company_ids: "123, 456", date_posted: "pastWeek" },
    };
    const { payload } = toSearchRequest(values, sources, null, "p-1");
    expect(payload.source_queries?.adzuna).toMatchObject({
      title: "Engineer",
      options: { title_only: true, distance_km: 25 },
    });
    expect(Object.keys(payload.source_queries?.adzuna?.options ?? {})).not.toContain("sort_by");
    expect(payload.source_queries?.apify_linkedin?.options).toMatchObject({
      company_ids: ["123", "456"],
      date_posted: "pastWeek",
    });
  });

  it("counts an options-only spec as content", () => {
    const linkedinOnly = [
      source({
        name: "apify_linkedin",
        is_official_api: false,
        supports_exclusions: false,
        filters: linkedinFilters,
      }),
    ];
    const values = baseValues(linkedinOnly);
    values.queries.apify_linkedin = {
      title: "",
      skills: "",
      exclude: "",
      options: { date_posted: "pastWeek" },
    };
    const { payload, missing } = toSearchRequest(values, linkedinOnly, null, "p-1");
    expect(missing).toEqual([]);
    expect(payload.source_queries?.apify_linkedin?.options).toEqual({
      date_posted: "pastWeek",
    });
  });
});

describe("optionsFromStored", () => {
  it("converts stored native types to form values", () => {
    const src = source({ name: "adzuna", filters: adzunaFilters });
    const options = optionsFromStored(
      { title_only: true, distance_km: 25, sort_by: "date" },
      src,
    );
    expect(options).toEqual({
      title_only: true,
      distance_km: "25",
      sort_by: "date",
    });
  });

  it("renders multiselect lists as comma-separated strings", () => {
    const src = source({
      name: "apify_linkedin",
      is_official_api: false,
      supports_exclusions: false,
      filters: linkedinFilters,
    });
    const options = optionsFromStored(
      { company_ids: ["123", "456"] },
      src,
    );
    expect(options).toEqual({ company_ids: "123, 456" });
  });

  it("ignores keys the source does not declare", () => {
    const src = source({ name: "adzuna", filters: adzunaFilters });
    const options = optionsFromStored({ company_ids: ["1"] }, src);
    expect(options).toEqual({});
  });

  it("returns an empty record for no stored options", () => {
    const src = source({ name: "adzuna", filters: adzunaFilters });
    expect(optionsFromStored(undefined, src)).toEqual({});
  });
});
