import type { components } from "./schema";
import { apiFetch, apiFetchVoid, apiFetchWithTotal } from "./client";

type Schemas = components["schemas"];

export type AgentSessionSummary = Schemas["AgentSessionSummary"];
export type AgentSession = Schemas["AgentSessionResponse"];
export type AgentMessage = Schemas["AgentMessageResponse"];
export type AgentTurn = Schemas["AgentTurnResponse"];
export type AgentCitation = Schemas["Citation"];
export type AgentGrounding = Schemas["Grounding"];
export type AgentPinnedJob = Schemas["PinnedJob"];

export interface AgentSessionCreate {
  profile_id: string;
  match_id?: string;
  style_notes?: string;
}

const BASE = "/api/agent/sessions";
const ANSWER_TIMEOUT_MS = 180_000;

function path(id: string, suffix = ""): string {
  return `${BASE}/${encodeURIComponent(id)}${suffix}`;
}

export function listAgentSessions(
  profileId?: string,
): Promise<{ items: AgentSessionSummary[]; total: number }> {
  const query = new URLSearchParams({ limit: "50" });
  if (profileId !== undefined) query.set("profile_id", profileId);
  return apiFetchWithTotal<AgentSessionSummary[]>(`${BASE}?${query.toString()}`);
}

export function createAgentSession(payload: AgentSessionCreate): Promise<AgentSessionSummary> {
  return apiFetch<AgentSessionSummary>(BASE, { method: "POST", body: JSON.stringify(payload) });
}

export function getAgentSession(id: string): Promise<AgentSession> {
  return apiFetch<AgentSession>(path(id));
}

export function deleteAgentSession(id: string): Promise<void> {
  return apiFetchVoid(path(id), { method: "DELETE" });
}

export function sendAgentMessage(id: string, content: string): Promise<AgentTurn> {
  return apiFetch<AgentTurn>(path(id, "/messages"), {
    method: "POST",
    body: JSON.stringify({ content }),
    timeoutMs: ANSWER_TIMEOUT_MS,
  });
}
