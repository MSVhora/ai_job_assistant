import { describe, expect, it } from "vitest";

import type { Achievement } from "@/lib/api";

import {
  approvalBlockers,
  employerSource,
  repositoryUrl,
  flagLabel,
  formatRevisionDiff,
  isStale,
  metricViews,
  parseSkills,
  pendingMetricCount,
} from "./achievement-view";

function achievement(overrides: Partial<Achievement> = {}): Achievement {
  return {
    id: "a1",
    status: "draft",
    origin: "ai_extracted",
    title: "Faster import",
    situation: "s",
    task: "t",
    action: "a",
    result: null,
    metrics: [],
    skills: [],
    impact_type: "performance",
    difficulty: 3,
    project_key: "ada/engine",
    employer_ref: null,
    time_start: null,
    time_end: null,
    review_flags: [],
    derived_from_private: false,
    edited_by_user: false,
    evidence_stale_at: null,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    evidence: [{ item_id: "i1", role: "primary", quote: null }],
    ...overrides,
  };
}

describe("metricViews", () => {
  it("narrows loose metric JSON and defaults unknown verification to needs_confirmation", () => {
    const views = metricViews(
      achievement({
        metrics: [
          { text: "42 to 9 minutes", source_quote: "from 42 to 9", verified: "evidence" },
          { text: "5 retries", verified: "user" },
          { text: 7, verified: "weird" },
        ],
      }),
    );

    expect(views).toEqual([
      { index: 0, text: "42 to 9 minutes", sourceQuote: "from 42 to 9", verified: "evidence" },
      { index: 1, text: "5 retries", sourceQuote: null, verified: "user" },
      { index: 2, text: "", sourceQuote: null, verified: "needs_confirmation" },
    ]);
  });

  it("counts pending metrics", () => {
    expect(
      pendingMetricCount(
        achievement({ metrics: [{ verified: "needs_confirmation" }, { verified: "user" }] }),
      ),
    ).toBe(1);
  });
});

describe("approvalBlockers", () => {
  it("lists what stops an approval", () => {
    expect(approvalBlockers(achievement())).toEqual([]);
    expect(approvalBlockers(achievement({ evidence: [] }))).toEqual([
      "Link at least one piece of evidence",
    ]);
    expect(
      approvalBlockers(
        achievement({ metrics: [{ verified: "needs_confirmation" }, { verified: "weird" }] }),
      ),
    ).toEqual(["Confirm 2 metrics"]);
    expect(approvalBlockers(achievement({ evidence: undefined as never }))).toHaveLength(1);
  });
});

describe("small helpers", () => {
  it("labels known flags and passes unknown ones through", () => {
    expect(flagLabel("contains_redaction_placeholder")).toMatch(/placeholder/);
    expect(flagLabel("something_new")).toBe("something_new");
  });

  it("detects stale evidence", () => {
    expect(isStale(achievement())).toBe(false);
    expect(isStale(achievement({ evidence_stale_at: "2026-10-02T00:00:00Z" }))).toBe(true);
  });

  it("parses a comma separated skill list without blanks or duplicates", () => {
    expect(parseSkills(" Go, Rust ,, Go ,  ")).toEqual(["Go", "Rust"]);
    expect(parseSkills("")).toEqual([]);
  });

  it("renders revision diffs as readable lines", () => {
    expect(formatRevisionDiff({ title: ["A", "B"], bulk: true })).toEqual([
      'title: "A" → "B"',
      "bulk: true",
    ]);
  });
});

describe("repositoryUrl and employerSource", () => {
  it("links only owner/repo project keys", () => {
    expect(repositoryUrl("ada/engine")).toBe("https://github.com/ada/engine");
    expect(repositoryUrl("resume:Acme Corp")).toBeNull();
    expect(repositoryUrl("a b/c")).toBeNull();
    expect(repositoryUrl(null)).toBeNull();
  });

  it("reads who set an employer", () => {
    expect(employerSource({ company: "A", source: "user" })).toBe("user");
    expect(employerSource({ company: "A", source: "scope" })).toBe("scope");
    expect(employerSource({ company: "A", source: "suggested" })).toBe("suggested");
    expect(employerSource({ company: "A" })).toBeNull();
    expect(employerSource(null)).toBeNull();
  });
});
