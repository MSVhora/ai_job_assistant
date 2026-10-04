import { describe, expect, it } from "vitest";

import type { ResumeDocument } from "@/lib/api";

import {
  availableCount,
  blockToText,
  commentsFor,
  notIncludedRows,
  pageUsageLine,
} from "./resume-view";

function bullet(id: string, text: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    text,
    achievement_id: null,
    evidence_ids: [],
    metric_ids: [],
    from_private: false,
    score: 0.5,
    origin: "generated",
    check: "passed",
    pinned: false,
    approved_anyway: false,
    flags: [],
    ...extra,
  };
}

function document(overrides: Record<string, unknown> = {}): ResumeDocument {
  return {
    id: "d1",
    page_target: 2,
    content: {
      basics: { full_name: "Ada" },
      skills: [],
      education: [],
      awards: [],
      certificates: [],
      extra_sections: [],
      projects: [],
      work: [
        {
          id: "w1",
          company: "Acme",
          title: "Engineer",
          start_date: "2020-01",
          end_date: null,
          is_current: true,
          highlights: [
            bullet("b1", "Cut import time by 40%"),
            bullet("b2", "Wrote the runbook"),
            bullet("b3", "Unverified claim", {
              check: "needs_review",
              flags: ["number not in evidence"],
            }),
          ],
        },
      ],
    },
    layout: {
      pages: 1,
      included_ids: ["b1"],
      short_on_evidence: false,
      steps: [],
      not_included: [
        { id: "b2", priority: 0.4, reason: "did_not_fit" },
        { id: "b3", priority: 0.3, reason: "needs_review" },
        { id: "a1", priority: 0.2, reason: "not_written" },
        { id: "w0", priority: 0.1, reason: "overlap_omitted" },
      ],
    },
    generation: { pool: [{ achievement_id: "a1", title: "Migrated billing", written: false }] },
    comments: [],
    ...overrides,
  } as unknown as ResumeDocument;
}

describe("notIncludedRows", () => {
  it("describes each unplaced item and leaves overlapping roles to their own card", () => {
    const rows = notIncludedRows(document());

    expect(rows.map((row) => [row.id, row.kind, row.reason, row.label])).toEqual([
      ["b2", "bullet", "did_not_fit", "Wrote the runbook"],
      ["b3", "bullet", "needs_review", "Unverified claim"],
      ["a1", "achievement", "not_written", "Migrated billing"],
    ]);
    expect(rows[1]?.flags).toEqual(["number not in evidence"]);
    expect(rows[0]?.context).toBe("Engineer at Acme");
  });

  it("counts only what could still be added", () => {
    expect(availableCount(notIncludedRows(document()))).toBe(2);
  });
});

describe("pageUsageLine", () => {
  it("shows pages used and how many more achievements are available", () => {
    expect(pageUsageLine(document(), 2)).toBe("1 of 2 pages — 2 more achievements available.");
  });

  it("says when everything available is already in", () => {
    const short = document({ layout: { ...document().layout, short_on_evidence: true } });

    expect(pageUsageLine(short, 0)).toContain("everything available is included");
  });

  it("explains an empty layout", () => {
    const empty = document({ layout: { ...document().layout, pages: null } });

    expect(pageUsageLine(empty, 0)).toContain("Nothing fits 2 pages yet");
  });
});

describe("blockToText", () => {
  it("copies only the included bullets, in plain text or Markdown", () => {
    const block = document().content.work[0];
    if (block === undefined) throw new Error("fixture");

    expect(blockToText(block, new Set(["b1"]), "text")).toBe(
      "Engineer at Acme\n2020-01 - Present\n- Cut import time by 40%",
    );
    expect(blockToText(block, new Set(["b1"]), "markdown").startsWith("### Engineer at Acme")).toBe(
      true,
    );
  });
});

describe("commentsFor", () => {
  it("separates section comments from bullet comments", () => {
    const comments = [
      { id: "c1", target: { section: "work", block_id: "w1" } },
      { id: "c2", target: { section: "work", block_id: "w1", bullet_id: "b1" } },
    ] as never;

    expect(commentsFor(comments, "w1", null).map((c) => c.id)).toEqual(["c1"]);
    expect(commentsFor(comments, "w1", "b1").map((c) => c.id)).toEqual(["c2"]);
  });
});
