"use client";

import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import type { EmployerOption, EvidenceScope, ScopeUpdateItem } from "@/lib/api";
import { employerKey, employerLabel } from "@/lib/evidence-progress";

const CONTENT_LEVELS = [
  { value: "messages_and_prs", label: "Messages and PRs" },
  { value: "metadata_only", label: "Metadata only" },
] as const;

function optionKey(option: EmployerOption): string {
  return option.kind === "personal"
    ? "personal"
    : `${option.company ?? ""}|${option.start_date ?? ""}`;
}

function optionRef(option: EmployerOption): Record<string, unknown> {
  return option.kind === "personal"
    ? { kind: "personal" }
    : { company: option.company, start_date: option.start_date };
}

export function ScopeRow({
  scope,
  employers,
  disabled,
  onChange,
  onToggle,
}: {
  scope: EvidenceScope;
  employers: EmployerOption[];
  disabled: boolean;
  onChange: (update: ScopeUpdateItem) => void;
  onToggle: (scope: EvidenceScope, enabled: boolean) => void;
}) {
  const suggestion = scope.suggested_employer ?? null;
  const synced = scope.last_synced_at !== null;
  const changeEmployer = (key: string) => {
    const match = employers.find((option) => optionKey(option) === key);
    onChange({ ref: scope.ref, employer_ref: match === undefined ? null : optionRef(match) });
  };
  return (
    <li className="flex flex-col gap-2 rounded-2xl border border-gray-200 bg-white p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <input
          type="checkbox"
          aria-label={`Sync ${scope.ref}`}
          checked={scope.enabled}
          disabled={disabled}
          onChange={(event) => {
            onToggle(scope, event.target.checked);
          }}
          className="h-4 w-4 rounded border-gray-300 text-violet-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-gray-900">{scope.ref}</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {scope.is_private && <Badge variant="warn">Private repo</Badge>}
            {scope.is_fork && <Badge>Fork</Badge>}
            {scope.is_new && <Badge variant="ai">New</Badge>}
            {scope.sync_state === "failed" && <Badge variant="danger">Last sync failed</Badge>}
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label={`Content level for ${scope.ref}`}
          value={scope.content_level}
          disabled={disabled}
          className="w-44"
          onChange={(event) => {
            onChange({
              ref: scope.ref,
              content_level:
                event.target.value === "metadata_only" ? "metadata_only" : "messages_and_prs",
            });
          }}
        >
          {CONTENT_LEVELS.map((level) => (
            <option key={level.value} value={level.value}>
              {level.label}
            </option>
          ))}
        </Select>
        {synced && (
          <Select
            aria-label={`Employer for ${scope.ref}`}
            value={employerKey(scope.employer_ref)}
            disabled={disabled}
            className="w-56"
            onChange={(event) => {
              changeEmployer(event.target.value);
            }}
          >
            <option value="">Unmapped (treated as a project)</option>
            {employers.map((option) => (
              <option key={optionKey(option)} value={optionKey(option)}>
                {option.label}
              </option>
            ))}
          </Select>
        )}
        {synced && suggestion !== null && scope.employer_ref === null && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              onChange({ ref: scope.ref, employer_ref: suggestion });
            }}
            className="rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Suggested: {employerLabel(suggestion)} — use
          </button>
        )}
      </div>
    </li>
  );
}
