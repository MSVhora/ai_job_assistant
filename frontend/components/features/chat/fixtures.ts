import type { AgentCitation, AgentGrounding, AgentMessage, AgentSession } from "@/lib/api";

export function grounding(overrides: Partial<AgentGrounding> = {}): AgentGrounding {
  return {
    status: "grounded",
    flagged_sentences: [],
    gaps: [],
    repaired: false,
    used_private: false,
    judge_unavailable: false,
    no_evidence: false,
    error: false,
    ...overrides,
  };
}

export function citation(marker: string, overrides: Partial<AgentCitation> = {}): AgentCitation {
  return {
    marker,
    kind: marker.startsWith("A") ? "achievement" : "evidence",
    label: `Source ${marker}`,
    achievement_id: null,
    evidence_item_id: null,
    url: null,
    quote: null,
    private: false,
    ...overrides,
  };
}

export function message(
  id: string,
  role: "user" | "assistant",
  content: string,
  overrides: Partial<AgentMessage> = {},
): AgentMessage {
  return {
    id,
    session_id: "s1",
    role,
    content,
    citations: [],
    grounding: grounding({ status: "not_applicable" }),
    created_at: "2026-10-05T10:00:00Z",
    ...overrides,
  };
}

export function session(overrides: Partial<AgentSession> = {}): AgentSession {
  return {
    id: "s1",
    profile_id: "p1",
    match_id: null,
    title: "Interview practice",
    style_notes: null,
    summary: null,
    job: null,
    messages: [],
    created_at: "2026-10-05T10:00:00Z",
    updated_at: "2026-10-05T10:00:00Z",
    ...overrides,
  };
}
