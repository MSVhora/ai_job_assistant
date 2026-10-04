import type { ResumeBullet, ResumeDocument } from "@/lib/api";

export function bullet(
  id: string,
  text: string,
  overrides: Partial<ResumeBullet> = {},
): ResumeBullet {
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
    ...overrides,
  };
}

export function resumeDocument(overrides: Partial<ResumeDocument> = {}): ResumeDocument {
  return {
    id: "d1",
    profile_id: "p1",
    match_id: null,
    title: "Ada Lovelace — Engineer",
    page_target: 2,
    status: "draft",
    version: 3,
    updated_at: "2026-10-04T00:00:00Z",
    created_at: "2026-10-04T00:00:00Z",
    jd_weight: 0.3,
    template: "classic",
    content: {
      basics: { full_name: "Ada Lovelace", email: "ada@example.com", links: [] },
      skills: ["Python", "SQL"],
      education: [{ institution: "Analytical College", degree: "BSc" }],
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
            bullet("b1", "Cut the nightly import from 42 to 9 minutes", {
              evidence_ids: ["i1"],
              from_private: true,
            }),
            bullet("b2", "Wrote the on-call runbook"),
            bullet("b3", "Reduced cloud spend", {
              check: "needs_review",
              flags: ["figure not in evidence"],
            }),
          ],
        },
      ],
    },
    layout: {
      pages: 1,
      preset: "P0",
      font_pt: 10.5,
      margin_in: 0.7,
      included_ids: ["b1"],
      short_on_evidence: false,
      steps: ["P0: 1 of 1 bullets, 1 page(s)", "chose P0"],
      not_included: [
        { id: "b2", priority: 0.4, reason: "did_not_fit" },
        { id: "b3", priority: 0.3, reason: "needs_review" },
        { id: "a1", priority: 0.2, reason: "not_written" },
      ],
    },
    comments: [],
    generation: {
      tailoring_strength: "balanced",
      exclude_private: false,
      pool: [
        {
          achievement_id: "a1",
          block_id: "w1",
          title: "Migrated billing",
          priority: 0.2,
          rank: 3,
          written: false,
        },
      ],
      omitted_roles: [],
      included_roles: ["w1"],
      gaps: [],
      warnings: [],
      unplaced_count: 0,
      private_bullet_count: 1,
      usage: { calls: 0, prompt_tokens: 0, completion_tokens: 0, cache_hits: 0, cache_misses: 0 },
    },
    ...overrides,
  };
}
