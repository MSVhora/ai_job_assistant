import { apiFetch, apiFetchWithTotal } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Achievement = Schemas["AchievementResponse"];
export type AchievementStatus = Schemas["AchievementStatus"];
export type AchievementUpdate = Schemas["AchievementUpdate"];
export type EvidenceLink = Schemas["EvidenceLinkResponse"];
export type BulkEligible = Schemas["BulkEligibleResponse"];
export type BulkApproveResult = Schemas["BulkApproveResponse"];
export type BulkTransitionResult = Schemas["BulkTransitionResponse"];
export type AchievementGroups = Schemas["AchievementGroupsResponse"];
export type EmployerGroup = Schemas["EmployerGroup"];
export type RepositoryGroup = Schemas["RepositoryGroup"];
export type MergeProposal = Schemas["MergeProposalResponse"];
export type MergeRequest = Schemas["MergeRequest"];
export type SplitRequest = Schemas["SplitRequest"];
export type ConfirmMetricRequest = Schemas["ConfirmMetricRequest"];
export type EvidenceLinkCreate = Schemas["EvidenceLinkCreate"];
export type Revision = Schemas["RevisionResponse"];

export type AchievementAction =
  "approve" | "reject" | "archive" | "unapprove" | "restore" | "acknowledge";

export interface AchievementListParams {
  status: AchievementStatus;
  stale?: boolean | undefined;
  private?: boolean | undefined;
  project_key?: string | undefined;
  employer?: string | undefined;
  impact_type?: string | undefined;
  has_metric?: boolean | undefined;
  employer_kind?: "personal" | "unassigned" | undefined;
  limit?: number | undefined;
  offset?: number | undefined;
}

const BASE = "/api/achievements";

function path(achievementId: string, suffix = ""): string {
  return `${BASE}/${encodeURIComponent(achievementId)}${suffix}`;
}

export async function listAchievementsPage(
  params: AchievementListParams,
): Promise<{ items: Achievement[]; total: number }> {
  const query = new URLSearchParams({ status: params.status });
  for (const [key, value] of Object.entries(params)) {
    if (key !== "status" && value !== undefined) query.set(key, String(value));
  }
  return apiFetchWithTotal<Achievement[]>(`${BASE}?${query.toString()}`);
}

export async function getAchievement(achievementId: string): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId));
}

export async function editAchievement(
  achievementId: string,
  payload: AchievementUpdate,
): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId), {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function runAchievementAction(
  achievementId: string,
  action: AchievementAction,
): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId, `/${action}`), { method: "POST" });
}

export async function confirmMetric(
  achievementId: string,
  payload: ConfirmMetricRequest,
): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId, "/confirm-metric"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function linkEvidence(
  achievementId: string,
  payload: EvidenceLinkCreate,
): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId, "/evidence"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function unlinkEvidence(achievementId: string, itemId: string): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId, `/evidence/${encodeURIComponent(itemId)}`), {
    method: "DELETE",
  });
}

export async function splitAchievement(
  achievementId: string,
  payload: SplitRequest,
): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId, "/split"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function mergeAchievements(payload: MergeRequest): Promise<Achievement> {
  return apiFetch<Achievement>(`${BASE}/merge`, { method: "POST", body: JSON.stringify(payload) });
}

export async function listMergeProposals(): Promise<MergeProposal[]> {
  return apiFetch<MergeProposal[]>(`${BASE}/merge-proposals`);
}

export async function listRevisions(achievementId: string): Promise<Revision[]> {
  return apiFetch<Revision[]>(path(achievementId, "/revisions?limit=100"));
}

export async function getBulkEligible(): Promise<BulkEligible> {
  return apiFetch<BulkEligible>(`${BASE}/bulk-approve/eligible`);
}

export async function bulkApprove(ids: string[]): Promise<BulkApproveResult> {
  return apiFetch<BulkApproveResult>(`${BASE}/bulk-approve`, {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
}

export async function bulkReject(ids: string[]): Promise<BulkTransitionResult> {
  return apiFetch<BulkTransitionResult>(`${BASE}/bulk-reject`, {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
}

export async function bulkArchive(ids: string[]): Promise<BulkTransitionResult> {
  return apiFetch<BulkTransitionResult>(`${BASE}/bulk-archive`, {
    method: "POST",
    body: JSON.stringify({ ids }),
  });
}

export async function getAchievementGroups(): Promise<AchievementGroups> {
  return apiFetch<AchievementGroups>(`${BASE}/groups`);
}

export async function getImpactQueue(): Promise<{ items: Achievement[]; total: number }> {
  return apiFetchWithTotal<Achievement[]>(`${BASE}/impact-queue`);
}

export async function addImpact(achievementId: string, text: string): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId, "/impact"), {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function skipImpact(achievementId: string): Promise<Achievement> {
  return apiFetch<Achievement>(path(achievementId, "/skip-impact"), { method: "POST" });
}
