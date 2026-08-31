import { apiFetch } from "./client";
import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type ResumeUploadResponse = components["schemas"]["ResumeUploadResponse"];
export type DraftProfileResponse = components["schemas"]["DraftProfileResponse"];
export type ProfileResponse = components["schemas"]["ProfileResponse"];
export type ProfileUpdateRequest = components["schemas"]["ProfileUpdateRequest"];
export type StructuredProfile = components["schemas"]["StructuredProfile"];
export type Preferences = components["schemas"]["Preferences"];

export { ApiError, apiFetch } from "./client";

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<ResumeUploadResponse>("/api/resume", { method: "POST", body });
}

export async function extractResume(resumeId: string): Promise<DraftProfileResponse> {
  return apiFetch<DraftProfileResponse>(`/api/resume/${resumeId}/extract`, { method: "POST" });
}

export async function getResumeDraft(resumeId: string): Promise<DraftProfileResponse> {
  return apiFetch<DraftProfileResponse>(`/api/resume/${resumeId}/draft`);
}

export async function getProfile(): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>("/api/profile");
}

export async function patchProfile(payload: ProfileUpdateRequest): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>("/api/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
