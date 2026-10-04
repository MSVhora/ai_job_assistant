import type { components } from "./schema";
import { apiFetch, apiFetchBlob, apiFetchText, apiFetchVoid, apiFetchWithTotal } from "./client";

type Schemas = components["schemas"];

export type ResumeDocument = Schemas["ResumeDocumentResponse"];
export type ResumeDocumentSummary = Schemas["ResumeDocumentSummary"];
type CreateSchema = Schemas["ResumeDocumentCreate"];
type Defaulted = "page_target" | "template" | "tailoring_strength" | "exclude_private";
export type ResumeDocumentCreate = Omit<CreateSchema, Defaulted> &
  Partial<Pick<CreateSchema, Defaulted>>;
export type ResumeLayout = Schemas["Layout"];
export type ResumeBullet = Schemas["Bullet"];
export type ResumeWorkEntry = Schemas["WorkEntry"];
export type ResumeProjectEntry = Schemas["ProjectEntry"];
export type ResumeContent = Schemas["ResumeContent"];
export type ResumeComment = Schemas["ResumeComment"];
export type CommentCreate = Schemas["CommentCreate"];
export type CommentTarget = Schemas["CommentTarget"];
export type ResumeConflict = Schemas["Conflict"];
export type ResumeConflicts = Schemas["ConflictsResponse"];
export type ResumeGap = Schemas["GapItem"];
export type OmittedRole = Schemas["OmittedRole"];
export type NotIncluded = Schemas["NotIncluded"];
export type PoolEntry = Schemas["PoolEntry"];
export type ExportFormat = "text" | "markdown" | "json_resume";
export type TailoringStrength = Schemas["ResumeDocumentCreate"]["tailoring_strength"];
export type ResumeTemplate = Schemas["ResumeDocumentCreate"]["template"];

const BASE = "/api/resume-documents";

function path(id: string, suffix = ""): string {
  return `${BASE}/${encodeURIComponent(id)}${suffix}`;
}

function send<T>(url: string, method: string, body?: unknown): Promise<T> {
  return apiFetch<T>(url, {
    method,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}

export interface ListResumeDocumentsParams {
  profileId?: string | undefined;
  limit?: number | undefined;
  offset?: number | undefined;
}

export function listResumeDocuments(
  params: ListResumeDocumentsParams = {},
): Promise<{ items: ResumeDocumentSummary[]; total: number }> {
  const query = new URLSearchParams();
  if (params.profileId !== undefined) query.set("profile_id", params.profileId);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiFetchWithTotal<ResumeDocumentSummary[]>(`${BASE}${suffix}`);
}

export function createResumeDocument(payload: ResumeDocumentCreate): Promise<ResumeDocument> {
  return send<ResumeDocument>(BASE, "POST", payload);
}

export function getResumeDocument(id: string): Promise<ResumeDocument> {
  return apiFetch<ResumeDocument>(path(id));
}

export function updateResumeTemplate(
  id: string,
  template: ResumeTemplate,
): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id), "PATCH", { template });
}

export function deleteResumeDocument(id: string): Promise<void> {
  return apiFetchVoid(path(id), { method: "DELETE" });
}

export function fitResumeDocument(id: string): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, "/fit"), "POST");
}

export function regenerateResumeDocument(id: string, blockId?: string): Promise<ResumeDocument> {
  return send<ResumeDocument>(
    path(id, "/regenerate"),
    "POST",
    blockId === undefined ? undefined : { block_id: blockId },
  );
}

export function pinResumeBullet(
  id: string,
  bulletId: string,
  pinned: boolean,
): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, `/bullets/${encodeURIComponent(bulletId)}`), "PATCH", {
    pinned,
  });
}

export function editResumeBullet(
  id: string,
  bulletId: string,
  text: string,
): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, `/bullets/${encodeURIComponent(bulletId)}`), "PATCH", {
    text,
  });
}

export function removeResumeBullet(id: string, bulletId: string): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, `/bullets/${encodeURIComponent(bulletId)}`), "DELETE");
}

export function approveResumeBulletAnyway(id: string, bulletId: string): Promise<ResumeDocument> {
  return send<ResumeDocument>(
    path(id, `/bullets/${encodeURIComponent(bulletId)}/approve-anyway`),
    "POST",
  );
}

export function includeRoleAnyway(id: string, blockId: string): Promise<ResumeDocument> {
  return send<ResumeDocument>(
    path(id, `/roles/${encodeURIComponent(blockId)}/include-anyway`),
    "POST",
  );
}

export function writeAchievementBullet(id: string, achievementId: string): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, `/write/${encodeURIComponent(achievementId)}`), "POST");
}

export function addResumeComment(id: string, payload: CommentCreate): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, "/comments"), "POST", payload);
}

export function deleteResumeComment(id: string, commentId: string): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, `/comments/${encodeURIComponent(commentId)}`), "DELETE");
}

export function applyResumeComments(id: string): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, "/apply-comments"), "POST");
}

export function getResumeConflicts(id: string): Promise<ResumeConflicts> {
  return apiFetch<ResumeConflicts>(path(id, "/conflicts"));
}

export function resolveResumeConflict(
  id: string,
  key: string,
  action: "keep_as_is" | "reopen",
): Promise<ResumeDocument> {
  return send<ResumeDocument>(path(id, `/conflicts/${encodeURIComponent(key)}/resolve`), "POST", {
    action,
  });
}

export function exportResumeDocument(id: string, format: ExportFormat): Promise<string> {
  return apiFetchText(path(id, `/export?format=${format}`));
}

export function generateResumePdf(id: string): Promise<Blob> {
  return apiFetchBlob(path(id, "/render"), { method: "POST", timeoutMs: 60_000 });
}
