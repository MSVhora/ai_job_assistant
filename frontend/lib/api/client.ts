const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 30_000;

const STATUS_FALLBACK_MESSAGES: Record<number, string> = {
  413: "That file is too large to upload.",
  415: "That file type is not supported — upload a PDF or DOCX resume.",
  422: "The request was invalid — check your input and try again.",
  502: "The AI provider could not complete the request — try again in a moment.",
  503: "The AI provider is not available — check your API key in the backend .env.",
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class ExtractionFailedError extends ApiError {
  readonly resumeId: string;

  constructor(resumeId: string, status: number, message: string) {
    super(status, message);
    this.name = "ExtractionFailedError";
    this.resumeId = resumeId;
  }
}

function formatValidationDetail(detail: unknown[]): string {
  const parts: string[] = [];
  for (const item of detail) {
    if (typeof item !== "object" || item === null) continue;
    const entry = item as Record<string, unknown>;
    const location = Array.isArray(entry.loc)
      ? entry.loc.filter((part) => part !== "body").join(".")
      : "";
    const message = String(entry.msg ?? "invalid value");
    parts.push(location === "" ? message : `${location}: ${message}`);
  }
  if (parts.length === 0) return STATUS_FALLBACK_MESSAGES[422];
  return `Invalid input — ${parts.join("; ")}`;
}

async function errorMessage(response: Response, path: string): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body) {
      const detail: unknown = body.detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) return formatValidationDetail(detail);
    }
  } catch {
    // fall through to the fallback message
  }
  return STATUS_FALLBACK_MESSAGES[response.status] ?? `API error ${response.status} on ${path}`;
}

type ApiFetchInit = RequestInit & { timeoutMs?: number };

export async function apiFetch<T>(path: string, init?: ApiFetchInit): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...requestInit } = init ?? {};
  let response: Response;
  const headers = new Headers(requestInit.headers);
  const isFormData = requestInit.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const signal = requestInit.signal ?? AbortSignal.timeout(timeoutMs);
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...requestInit, headers, signal });
  } catch (cause) {
    if (cause instanceof Error && cause.name === "TimeoutError") {
      throw new ApiError(0, "The request timed out — try again.");
    }
    throw new ApiError(0, `network error: ${cause instanceof Error ? cause.message : "unknown"}`);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response, path));
  }
  return (await response.json()) as T;
}
