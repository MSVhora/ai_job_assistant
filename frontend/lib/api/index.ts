import { ApiError, ExtractionFailedError, apiFetch } from "./client";
import type { components, operations } from "./schema";

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
export type SetupCheck = components["schemas"]["SetupCheckResponse"];
export type SourceInfo = components["schemas"]["SourceInfoResponse"];
export type JobSearchRequest = components["schemas"]["JobSearchRequest"];
export type JobSearchStart = components["schemas"]["JobSearchStartResponse"];
export type JobSearchStatus = components["schemas"]["JobSearchStatusResponse"];
export type SourceQuerySpec = components["schemas"]["SourceQuerySpec"];
export type StoredSearchQueries = components["schemas"]["StoredSearchQueries"];
export type SearchQueriesResponse = components["schemas"]["SearchQueriesResponse"];
export type JobPostingSummary = components["schemas"]["JobPostingSummary"];
export type MatchResponse = components["schemas"]["MatchResponse"];
export type MatchingOutcome = components["schemas"]["MatchingOutcome"];
export type StoredPreferences = components["schemas"]["StoredPreferences"];
export type MatchListParams = operations["list_matches_api_matches_get"]["parameters"]["query"];

export { ApiError, ExtractionFailedError, apiFetch } from "./client";


export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<ResumeUploadResponse>("/api/resumes", {
    method: "POST",
    body,
    timeoutMs: 120_000,
  });
}

export async function extractResume(resumeId: string): Promise<DraftProfileResponse> {
  try {
    return await apiFetch<DraftProfileResponse>(`/api/resumes/${resumeId}/extract`, {
      method: "POST",
      timeoutMs: 120_000,
    });
  } catch (cause) {
    if (cause instanceof ApiError && cause.status !== 404) {
      throw new ExtractionFailedError(resumeId, cause.status, cause.message);
    }
    throw cause;
  }
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

export async function updatePreferences(
  profileId: string,
  payload: StoredPreferences,
): Promise<StoredPreferences> {
  return apiFetch<StoredPreferences>(
    `/api/profiles/${encodeURIComponent(profileId)}/preferences`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
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

export async function getSetupCheck(): Promise<SetupCheck> {
  return apiFetch<SetupCheck>("/api/setup/check", { method: "POST" });
}

export async function listSources(): Promise<SourceInfo[]> {
  return apiFetch<SourceInfo[]>("/api/sources");
}

export async function enableSource(
  name: string,
  acknowledgedDisclosure: boolean,
): Promise<SourceInfo> {
  return apiFetch<SourceInfo>(`/api/sources/${encodeURIComponent(name)}/enable`, {
    method: "POST",
    body: JSON.stringify({ acknowledged_disclosure: acknowledgedDisclosure }),
  });
}

export async function startJobSearch(payload: JobSearchRequest): Promise<JobSearchStart> {
  return apiFetch<JobSearchStart>("/api/jobs/search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getJobSearchStatus(searchId: string): Promise<JobSearchStatus> {
  return apiFetch<JobSearchStatus>(`/api/jobs/searches/${encodeURIComponent(searchId)}`);
}

export async function getSearchPostings(searchId: string): Promise<JobPostingSummary[]> {
  return apiFetch<JobPostingSummary[]>(
    `/api/jobs/searches/${encodeURIComponent(searchId)}/postings`,
  );
}

export async function listMatches(params: MatchListParams): Promise<MatchResponse[]> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  return apiFetch<MatchResponse[]>(`/api/matches?${query.toString()}`);
}

export async function regenerateSearchQueries(
  profileId: string,
  sources?: string[],
): Promise<SearchQueriesResponse> {
  return apiFetch<SearchQueriesResponse>(
    `/api/profiles/${encodeURIComponent(profileId)}/search-queries`,
    { method: "POST", body: JSON.stringify(sources ? { sources } : {}) },
  );
}
