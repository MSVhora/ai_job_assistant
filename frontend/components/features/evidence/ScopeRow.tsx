"use client";

import { EmployerSelect } from "@/components/features/employers/EmployerSelect";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import type { EmployerOption, EvidenceScope } from "@/lib/api";
import { findOption, keyForRef, optionRef } from "@/lib/employer-options";
import { employerLabel } from "@/lib/evidence-progress";
import { viewOf, type ScopePatch } from "@/lib/scope-draft";

const CONTENT_LEVELS = [
  { value: "messages_and_prs", label: "Messages and PRs" },
  { value: "metadata_only", label: "Metadata only" },
] as const;

export function ScopeRow({
  scope,
  patch,
  employers,
  disabled,
  onChange,
}: {
  scope: EvidenceScope;
  patch: ScopePatch | undefined;
  employers: EmployerOption[];
  disabled: boolean;
  onChange: (patch: ScopePatch) => void;
}) {
  const view = viewOf(scope, patch);
  const suggestion = scope.suggested_employer ?? null;
  const synced = scope.last_synced_at !== null;
  const changeEmployer = (key: string) => {
    const match = findOption(employers, key);
    onChange({ employer_ref: match === undefined ? null : optionRef(match) });
  };
  return (
    <li className="flex flex-col gap-2 rounded-2xl border border-gray-200 bg-white p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <input
          type="checkbox"
          aria-label={`Include ${scope.ref}`}
          checked={view.enabled}
          disabled={disabled || (!scope.visible && !view.enabled)}
          onChange={(event) => {
            onChange({ enabled: event.target.checked });
          }}
          className="h-4 w-4 rounded border-gray-300 text-violet-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-gray-900">{scope.ref}</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {scope.contributed && <Badge variant="success">Contributed</Badge>}
            {!scope.visible && <Badge variant="warn">No longer visible</Badge>}
            {scope.is_private && <Badge variant="warn">Private repo</Badge>}
            {scope.is_fork && <Badge>Fork</Badge>}
            {scope.is_new && <Badge variant="ai">New</Badge>}
            {scope.sync_state === "failed" && <Badge variant="danger">Last sync failed</Badge>}
            {patch !== undefined && <Badge variant="ai">Unsaved</Badge>}
          </div>
          {!scope.visible && (
            <p className="mt-1 text-xs text-amber-800">
              GitHub no longer lists this repository (access removed or deleted), so it cannot be
              synced. You can still deselect it.
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label={`Content level for ${scope.ref}`}
          value={view.content_level}
          disabled={disabled}
          className="w-44"
          onChange={(event) => {
            onChange({
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
          <EmployerSelect
            ariaLabel={`Employer for ${scope.ref}`}
            value={keyForRef(employers, view.employer_ref)}
            options={employers}
            noneLabel="Unmapped (treated as a project)"
            disabled={disabled}
            className="w-56"
            onChange={changeEmployer}
          />
        )}
        {synced && suggestion !== null && view.employer_ref === null && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              onChange({ employer_ref: suggestion });
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
