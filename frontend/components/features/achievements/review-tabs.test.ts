import { describe, expect, it } from "vitest";

import { NO_FILTERS, PAGE_SIZE, paramsForTab } from "./review-tabs";

describe("paramsForTab", () => {
  it("sends only the filters that are set", () => {
    expect(paramsForTab("draft", NO_FILTERS, 0)).toEqual({
      status: "draft",
      limit: PAGE_SIZE,
      offset: 0,
    });
  });

  it("maps the impact, metric, repository and employer choices to list params", () => {
    expect(
      paramsForTab(
        "draft",
        {
          privateOnly: true,
          repository: "acme/api",
          employer: "employer:Acme",
          impact: "revenue",
          metric: "no",
        },
        20,
      ),
    ).toEqual({
      status: "draft",
      limit: PAGE_SIZE,
      offset: 20,
      private: true,
      project_key: "acme/api",
      impact_type: "revenue",
      has_metric: false,
      employer: "Acme",
    });
  });

  it("reads the attention tab as stale approved achievements", () => {
    expect(paramsForTab("attention", NO_FILTERS, 0)).toMatchObject({
      status: "approved",
      stale: true,
    });
  });
});
