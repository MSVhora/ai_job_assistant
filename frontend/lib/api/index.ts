import { apiFetch } from "./client";
import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type ResumeUploadResponse = components["schemas"]["ResumeUploadResponse"];
export type DraftProfileResponse = components["schemas"]["DraftProfileResponse"];
export type ResumeSummaryResponse = components["schemas"]["ResumeSummaryResponse"];
export type ProfileResponse = components["schemas"]["ProfileResponse"];
export type ProfileSummary = components["schemas"]["ProfileSummary"];
export type ProfileCreate = components["schemas"]["ProfileCreate"];
export type ProfileUpdate = components["schemas"]["ProfileUpdate"];
export type StructuredProfile = components["schemas"]["StructuredProfile"];
export type GapFillMessage = components["schemas"]["GapFillMessage"];
export type GapFillResponse = components["schemas"]["GapFillResponse"];

export { ApiError, apiFetch } from "./client";

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<ResumeUploadResponse>("/api/resumes", { method: "POST", body });
}

export async function extractResume(resumeId: string): Promise<DraftProfileResponse> {
  return apiFetch<DraftProfileResponse>(`/api/resumes/${resumeId}/extract`, { method: "POST" });
}

export async function listResumes(): Promise<ResumeSummaryResponse[]> {
  return apiFetch<ResumeSummaryResponse[]>("/api/resumes");
}

export async function getResumeDraft(resumeId: string): Promise<DraftProfileResponse> {
  return apiFetch<DraftProfileResponse>(`/api/resumes/${resumeId}/draft`);
}

export async function listProfiles(): Promise<ProfileSummary[]> {
  return apiFetch<ProfileSummary[]>("/api/profiles");
}

export async function getProfile(profileId: string): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>(`/api/profiles/${profileId}`);
}

export async function createProfile(payload: ProfileCreate): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>("/api/profiles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateProfile(
  profileId: string,
  payload: ProfileUpdate,
): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>(`/api/profiles/${profileId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteProfile(profileId: string): Promise<void> {
  await apiFetch<unknown>(`/api/profiles/${profileId}`, { method: "DELETE" });
}

export async function gapFillTurn(
  profileId: string,
  messages: GapFillMessage[],
): Promise<GapFillResponse> {
  return apiFetch<GapFillResponse>(`/api/profiles/${profileId}/gap-fill`, {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
}
