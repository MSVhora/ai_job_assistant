import type { ExtractionRun, SyncRun } from "@/lib/api";

const ACTIVE = new Set(["pending", "running"]);

export interface ScopeProgress {
  ref: string;
  status: string;
  items: number;
  filtered: number;
  warning: string | null;
}

export interface ChunkProgress {
  created: number;
  embedded: number;
  embedFailed: number;
  pending: number;
}

export interface SyncView {
  status: string;
  mode: string;
  active: boolean;
  items: number;
  requests: number;
  scopes: ScopeProgress[];
  warnings: string[];
  chunks: ChunkProgress | null;
  staleFlagged: number;
  resumeAt: Date | null;
  error: string | null;
}

export interface ExtractionView {
  status: string;
  active: boolean;
  total: number;
  done: number;
  failed: number;
  achievements: number;
  rejected: number;
  cached: number;
  embedFailed: number;
  promptTokens: number;
  costUsd: number | null;
  error: string | null;
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function num(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

export function isActiveStatus(status: string | undefined): boolean {
  return status !== undefined && ACTIVE.has(status);
}

function viewScopes(progress: Record<string, unknown>): ScopeProgress[] {
  return Object.entries(record(progress.scopes))
    .map(([ref, raw]) => {
      const entry = record(raw);
      return {
        ref,
        status: text(entry.status) ?? "pending",
        items: num(entry.items),
        filtered: num(entry.filtered),
        warning: text(entry.warning),
      };
    })
    .sort((left, right) => left.ref.localeCompare(right.ref));
}

function viewChunks(value: unknown): ChunkProgress | null {
  const chunks = record(value);
  if (Object.keys(chunks).length === 0 || "error" in chunks) return null;
  return {
    created: num(chunks.created),
    embedded: num(chunks.embedded),
    embedFailed: num(chunks.embed_failed),
    pending: num(chunks.pending_embedding),
  };
}

export function viewSync(run: SyncRun): SyncView {
  const warnings = Array.isArray(run.progress.warnings)
    ? run.progress.warnings.filter((entry): entry is string => typeof entry === "string")
    : [];
  return {
    status: run.status,
    mode: run.mode,
    active: isActiveStatus(run.status),
    items: num(run.progress.items),
    requests: num(run.usage.requests),
    scopes: viewScopes(run.progress),
    warnings,
    chunks: viewChunks(run.progress.chunks),
    staleFlagged: num(run.progress.stale_flagged),
    resumeAt: run.resume_at === null ? null : new Date(run.resume_at),
    error: run.error,
  };
}

export function viewExtraction(run: ExtractionRun): ExtractionView {
  const cost = run.usage.cost_usd;
  return {
    status: run.status,
    active: isActiveStatus(run.status),
    total: num(run.progress.total),
    done: num(run.progress.done),
    failed: num(run.progress.failed),
    achievements: num(run.progress.achievements),
    rejected: num(run.progress.rejected),
    cached: num(run.progress.cached),
    embedFailed: num(run.progress.embed_failed),
    promptTokens: num(run.usage.prompt_tokens),
    costUsd: typeof cost === "number" ? cost : null,
    error: run.error,
  };
}

export function employerLabel(ref: Record<string, unknown> | null | undefined): string | null {
  if (ref === null || ref === undefined) return null;
  if (ref.kind === "personal") return "Personal / open source";
  const company = text(ref.company);
  if (company === null) return null;
  const start = text(ref.start_date);
  return start === null ? company : `${company} (${start})`;
}

export function employerKey(ref: Record<string, unknown> | null | undefined): string {
  if (ref === null || ref === undefined) return "";
  if (ref.kind === "personal") return "personal";
  const company = text(ref.company);
  return company === null ? "" : `${company}|${text(ref.start_date) ?? ""}`;
}

export function formatResumeAt(date: Date | null): string | null {
  if (date === null || Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
