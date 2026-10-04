import type { EmployerOption, EvidenceScope, EvidenceStatus, SyncRun } from "@/lib/api";

export function status(overrides: Partial<EvidenceStatus> = {}): EvidenceStatus {
  return {
    configured: true,
    login: "ada",
    acknowledged_at: null,
    last_synced_at: null,
    scopes_total: 2,
    scopes_enabled: 1,
    scopes_unmapped: 0,
    scopes_refreshed_at: "2026-10-02T09:00:00Z",
    latest_sync: null,
    ...overrides,
  };
}

export function scope(overrides: Partial<EvidenceScope> = {}): EvidenceScope {
  return {
    ref: "ada/engine",
    is_private: false,
    is_fork: false,
    description: null,
    pushed_at: null,
    enabled: false,
    is_new: false,
    content_level: "messages_and_prs",
    sync_state: "pending",
    last_synced_at: null,
    employer_ref: null,
    suggested_employer: null,
    contributed: false,
    visible: true,
    ...overrides,
  };
}

export function syncRun(overrides: Partial<SyncRun> = {}): SyncRun {
  return {
    id: "sync-1",
    status: "succeeded",
    mode: "incremental",
    progress: {},
    rate_limit: {},
    resume_at: null,
    error: null,
    usage: {},
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-03T10:00:00Z",
    ...overrides,
  };
}

export function employerOption(
  company: string,
  overrides: Partial<EmployerOption> = {},
): EmployerOption {
  return {
    kind: "experience",
    label: `${company} · 2020 – 2022`,
    company,
    start_date: null,
    key: company.toLowerCase(),
    entries: 1,
    span: "2020 – 2022",
    aliases: [company],
    merged_from: [],
    ...overrides,
  };
}

export const PERSONAL_OPTION: EmployerOption = {
  kind: "personal",
  label: "Personal / open source",
  company: null,
  start_date: null,
  key: "personal",
  entries: 0,
  span: null,
  aliases: [],
  merged_from: [],
};
