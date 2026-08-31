import { apiFetch } from "./client";
import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];

export { ApiError, apiFetch } from "./client";

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}
