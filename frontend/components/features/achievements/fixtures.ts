import type { Achievement, EvidenceItem } from "@/lib/api";

export function achievement(overrides: Partial<Achievement> = {}): Achievement {
  return {
    id: "a1",
    status: "draft",
    origin: "ai_extracted",
    title: "Faster nightly import",
    situation: "The import took 42 minutes.",
    task: "Reduce the runtime.",
    action: "Batched the writes.",
    result: "The import now takes 9 minutes.",
    metrics: [],
    skills: ["Python", "PostgreSQL"],
    impact_type: "performance",
    difficulty: 3,
    project_key: "ada/engine",
    employer_ref: null,
    time_start: "2024-06-01",
    time_end: null,
    review_flags: [],
    derived_from_private: false,
    edited_by_user: false,
    evidence_stale_at: null,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    evidence: [{ item_id: "i1", role: "primary", quote: "from 42 minutes to 9 minutes" }],
    ...overrides,
  };
}

export function item(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: "i1",
    kind: "pull_request",
    external_id: "ada/engine#7",
    project_key: "ada/engine",
    title: "Add the loader",
    body: "Cut the import from 42 minutes to 9 minutes.",
    url: "https://github.com/ada/engine/pull/7",
    occurred_at: "2024-06-01T00:00:00Z",
    authored_by_user: true,
    status: "kept",
    filter_reason: null,
    is_private: false,
    meta: {},
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    ...overrides,
  };
}

export const PENDING_METRIC = {
  text: "10x faster",
  source_quote: "ten times",
  verified: "needs_confirmation",
};
