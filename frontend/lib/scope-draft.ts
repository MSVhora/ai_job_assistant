import type { EvidenceScope, ScopeUpdateItem } from "@/lib/api";
import { employerKey } from "@/lib/evidence-progress";

export const SCOPE_UPDATE_BATCH = 200;

export interface ScopePatch {
  enabled?: boolean;
  content_level?: EvidenceScope["content_level"];
  employer_ref?: Record<string, unknown> | null;
}

/** Unsaved edits by repository ref; a ref is present only while it differs from the server. */
export type ScopeDraft = Readonly<Record<string, ScopePatch>>;

export interface ScopeView {
  enabled: boolean;
  content_level: EvidenceScope["content_level"];
  employer_ref: Record<string, unknown> | null;
}

export function viewOf(scope: EvidenceScope, patch: ScopePatch | undefined): ScopeView {
  return {
    enabled: patch?.enabled ?? scope.enabled,
    content_level: patch?.content_level ?? scope.content_level,
    employer_ref: patch?.employer_ref === undefined ? scope.employer_ref : patch.employer_ref,
  };
}

function without(draft: ScopeDraft, ref: string): ScopeDraft {
  return Object.fromEntries(Object.entries(draft).filter(([key]) => key !== ref));
}

/** Apply an edit and drop every field that now equals what is saved. */
export function withPatch(draft: ScopeDraft, scope: EvidenceScope, patch: ScopePatch): ScopeDraft {
  const merged: ScopePatch = { ...draft[scope.ref], ...patch };
  const kept: ScopePatch = {};
  if (merged.enabled !== undefined && merged.enabled !== scope.enabled) {
    kept.enabled = merged.enabled;
  }
  if (merged.content_level !== undefined && merged.content_level !== scope.content_level) {
    kept.content_level = merged.content_level;
  }
  if (
    merged.employer_ref !== undefined &&
    employerKey(merged.employer_ref) !== employerKey(scope.employer_ref)
  ) {
    kept.employer_ref = merged.employer_ref;
  }
  return Object.keys(kept).length === 0
    ? without(draft, scope.ref)
    : { ...draft, [scope.ref]: kept };
}

export function selectScopes(
  draft: ScopeDraft,
  scopes: EvidenceScope[],
  enabled: boolean,
): ScopeDraft {
  return scopes.reduce((next, scope) => withPatch(next, scope, { enabled }), draft);
}

export function toUpdates(draft: ScopeDraft): ScopeUpdateItem[] {
  return Object.entries(draft).map(([ref, patch]) => ({ ref, ...patch }));
}

export function changeCount(draft: ScopeDraft): number {
  return Object.keys(draft).length;
}

/** Private repositories this draft would switch on, which need the disclosure confirmation. */
export function newlyEnabledPrivate(draft: ScopeDraft, scopes: EvidenceScope[]): string[] {
  return scopes
    .filter((scope) => scope.is_private && !scope.enabled && draft[scope.ref]?.enabled === true)
    .map((scope) => scope.ref);
}

export function selectedCount(scopes: EvidenceScope[], draft: ScopeDraft): number {
  return scopes.filter((scope) => viewOf(scope, draft[scope.ref]).enabled).length;
}

export function filterScopes(scopes: EvidenceScope[], query: string): EvidenceScope[] {
  const needle = query.trim().toLowerCase();
  if (needle === "") return scopes;
  return scopes.filter((scope) => scope.ref.toLowerCase().includes(needle));
}

export function chunk<T>(items: T[], size: number): T[][] {
  const groups: T[][] = [];
  for (let start = 0; start < items.length; start += size) {
    groups.push(items.slice(start, start + size));
  }
  return groups;
}

export const SCOPE_PAGE_SIZES = [25, 50, 100] as const;

export interface PageSlice<T> {
  items: T[];
  page: number;
  pageCount: number;
  from: number;
  to: number;
  total: number;
}

/** One zero-based page of `items`; an out-of-range page is clamped rather than empty. */
export function paginate<T>(items: T[], page: number, size: number): PageSlice<T> {
  const total = items.length;
  const pageCount = Math.max(1, Math.ceil(total / size));
  const current = Math.min(Math.max(0, page), pageCount - 1);
  const start = current * size;
  return {
    items: items.slice(start, start + size),
    page: current,
    pageCount,
    from: total === 0 ? 0 : start + 1,
    to: Math.min(start + size, total),
    total,
  };
}
