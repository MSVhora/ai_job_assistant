import { apiFetch, apiFetchVoid, apiFetchWithTotal } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];
type Estimate = Schemas["CostEstimateResponse"];

export type EvidenceStatus = Schemas["EvidenceStatusResponse"];
export type EvidenceScope = Schemas["ScopeResponse"];
export type ScopeUpdateItem = Schemas["ScopeUpdateItem"];
export type EmployerOption = Schemas["EmployerOption"];
export type OwnerSummary = Schemas["OwnerSummary"];
export type EmployerMergeSuggestion = Schemas["EmployerMergeSuggestion"];
export type EmployerMergeSuggestions = Schemas["EmployerMergeSuggestionsResponse"];
export type EmployerMergeRequest = Schemas["EmployerMergeRequest"];
export type TokenCheck = Schemas["TokenCheckResponse"];
export type SyncRun = Schemas["SyncRunResponse"];
export type SyncStart = Schemas["SyncStartResponse"];
export type SyncMode = Schemas["SyncRequest"]["mode"];
export type EvidenceItem = Schemas["ItemResponse"];
export type NoteCreate = Schemas["NoteCreate"];
export type NoteUpdate = Schemas["NoteUpdate"];
export type LinkCreate = Schemas["LinkCreate"];
export type ResumeIngestResult = Schemas["ResumeIngestResponse"];
export type ChunkSummary = Schemas["ChunkSummaryResponse"];
export type ExtractionEstimate = Schemas["ExtractionEstimateResponse"];
export type ExtractionStart = Schemas["ExtractionStartResponse"];
export type ExtractionRun = Schemas["ExtractionRunResponse"];

const BASE = "/api/evidence";

export async function getEvidenceStatus(): Promise<EvidenceStatus> {
  return apiFetch<EvidenceStatus>(`${BASE}/github/status`);
}

export async function listGithubScopes(): Promise<EvidenceScope[]> {
  return apiFetch<EvidenceScope[]>(`${BASE}/github/scopes`, { timeoutMs: 60_000 });
}

export async function updateGithubScopes(
  scopes: ScopeUpdateItem[],
  acknowledgedDisclosure: boolean,
): Promise<EvidenceScope[]> {
  return apiFetch<EvidenceScope[]>(`${BASE}/github/scopes`, {
    method: "PATCH",
    body: JSON.stringify({ scopes, acknowledged_disclosure: acknowledgedDisclosure }),
  });
}

/** The token's scopes as of the last refresh; null until the list has been refreshed once. */
export async function getTokenCheck(): Promise<TokenCheck | null> {
  return apiFetch<TokenCheck | null>(`${BASE}/github/token`);
}

/** Asks GitHub for the repository list and stores it; takes several seconds. */
export async function refreshGithubScopes(): Promise<EvidenceScope[]> {
  return apiFetch<EvidenceScope[]>(`${BASE}/github/scopes/refresh`, {
    method: "POST",
    timeoutMs: 120_000,
  });
}

export async function mergeEmployers(payload: EmployerMergeRequest): Promise<EmployerOption[]> {
  return apiFetch<EmployerOption[]>(`${BASE}/employers/merges`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function unmergeEmployer(key: string): Promise<EmployerOption[]> {
  return apiFetch<EmployerOption[]>(`${BASE}/employers/merges/${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
}

export async function estimateEmployerMergeSuggestions(): Promise<Estimate> {
  return apiFetch<Estimate>(`${BASE}/employers/merge-suggestions/estimate`, {
    method: "POST",
  });
}

export async function suggestEmployerMerges(): Promise<EmployerMergeSuggestions> {
  return apiFetch<EmployerMergeSuggestions>(`${BASE}/employers/merge-suggestions`, {
    method: "POST",
    timeoutMs: 120_000,
  });
}

export async function listEmployers(): Promise<EmployerOption[]> {
  return apiFetch<EmployerOption[]>(`${BASE}/employers`);
}

export async function listOwners(): Promise<OwnerSummary[]> {
  return apiFetch<OwnerSummary[]>(`${BASE}/github/organizations`);
}

export async function setOwnerEmployer(
  owner: string,
  employerRef: Record<string, unknown> | null,
): Promise<OwnerSummary[]> {
  return apiFetch<OwnerSummary[]>(`${BASE}/github/organizations/${encodeURIComponent(owner)}`, {
    method: "PATCH",
    body: JSON.stringify({ employer_ref: employerRef }),
  });
}

export async function startGithubSync(mode: SyncMode): Promise<SyncStart> {
  return apiFetch<SyncStart>(`${BASE}/github/sync`, {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export async function getSync(syncId: string): Promise<SyncRun> {
  return apiFetch<SyncRun>(`${BASE}/syncs/${encodeURIComponent(syncId)}`);
}

export async function listSyncs(limit = 1): Promise<SyncRun[]> {
  return apiFetch<SyncRun[]>(`${BASE}/syncs?limit=${String(limit)}`);
}

export async function listNotes(): Promise<{ items: EvidenceItem[]; total: number }> {
  return apiFetchWithTotal<EvidenceItem[]>(`${BASE}/notes?limit=200`);
}

export async function createNote(payload: NoteCreate): Promise<EvidenceItem> {
  return apiFetch<EvidenceItem>(`${BASE}/notes`, { method: "POST", body: JSON.stringify(payload) });
}

export async function updateNote(noteId: string, payload: NoteUpdate): Promise<EvidenceItem> {
  return apiFetch<EvidenceItem>(`${BASE}/notes/${encodeURIComponent(noteId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteNote(noteId: string): Promise<void> {
  return apiFetchVoid(`${BASE}/notes/${encodeURIComponent(noteId)}`, { method: "DELETE" });
}

export async function createLink(payload: LinkCreate): Promise<EvidenceItem> {
  return apiFetch<EvidenceItem>(`${BASE}/links`, { method: "POST", body: JSON.stringify(payload) });
}

export async function ingestResume(profileId: string): Promise<ResumeIngestResult> {
  return apiFetch<ResumeIngestResult>(`${BASE}/resume/ingest`, {
    method: "POST",
    body: JSON.stringify({ profile_id: profileId }),
  });
}

export async function getChunkSummary(): Promise<ChunkSummary> {
  return apiFetch<ChunkSummary>(`${BASE}/chunks/summary`);
}

export async function getEvidenceItem(itemId: string): Promise<EvidenceItem> {
  return apiFetch<EvidenceItem>(`${BASE}/items/${encodeURIComponent(itemId)}`);
}

export async function estimateExtraction(): Promise<ExtractionEstimate> {
  return apiFetch<ExtractionEstimate>(`${BASE}/extract/estimate`, {
    method: "POST",
    timeoutMs: 60_000,
  });
}

export async function startExtraction(confirmedEstimateId: string): Promise<ExtractionStart> {
  return apiFetch<ExtractionStart>(`${BASE}/extract`, {
    method: "POST",
    body: JSON.stringify({ confirmed_estimate_id: confirmedEstimateId }),
  });
}

export async function listExtractionRuns(limit = 1): Promise<ExtractionRun[]> {
  return apiFetch<ExtractionRun[]>(`${BASE}/extract/runs?limit=${String(limit)}`);
}

export async function getExtractionRun(runId: string): Promise<ExtractionRun> {
  return apiFetch<ExtractionRun>(`${BASE}/extract/runs/${encodeURIComponent(runId)}`);
}
