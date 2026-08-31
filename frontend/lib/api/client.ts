const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function errorMessage(response: Response, path: string): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return body.detail;
    }
  } catch {
    // fall through to the generic message
  }
  return `API error ${response.status} on ${path}`;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const headers = new Headers(init?.headers);
  const isFormData = init?.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch (cause) {
    throw new ApiError(0, `network error: ${cause instanceof Error ? cause.message : "unknown"}`);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response, path));
  }
  return (await response.json()) as T;
}
