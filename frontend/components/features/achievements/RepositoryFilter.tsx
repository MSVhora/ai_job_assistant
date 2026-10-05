"use client";

import { Select } from "@/components/ui/select";
import { useEmployers, useGithubScopes } from "@/hooks/use-evidence-sync";
import type { EmployerOption, EvidenceScope } from "@/lib/api";
import { findOptionForRef } from "@/lib/employer-options";
import { employerKey, employerLabel } from "@/lib/evidence-progress";

import { RepositoryEmployerBar } from "./RepositoryEmployerBar";

/** "owner/repo — Employer": what each repository is attributed to, or that nothing is set. */
function optionLabel(scope: EvidenceScope, employers: EmployerOption[]): string {
  const known = findOptionForRef(employers, scope.employer_ref);
  const employer = known?.company ?? employerLabel(scope.employer_ref);
  return `${scope.ref} — ${employer ?? "no employer set"}`;
}

export function RepositoryFilter({
  value,
  onChange,
  allowed,
}: {
  value: string;
  onChange: (repository: string) => void;
  allowed?: ReadonlySet<string> | undefined;
}) {
  const scopes = useGithubScopes(true);
  const employers = useEmployers();
  const repositories = (scopes.data ?? [])
    .filter((scope) => scope.enabled || scope.last_synced_at !== null)
    .filter((scope) => allowed === undefined || allowed.has(scope.ref))
    .sort((left, right) => left.ref.localeCompare(right.ref));
  const chosen = repositories.find((scope) => scope.ref === value);

  if (repositories.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <label htmlFor="achievement-repository" className="text-sm text-gray-700">
          Repository
        </label>
        <Select
          id="achievement-repository"
          value={value}
          className="w-96 max-w-full"
          onChange={(event) => {
            onChange(event.target.value);
          }}
        >
          <option value="">All repositories</option>
          {repositories.map((scope) => (
            <option key={scope.ref} value={scope.ref}>
              {optionLabel(scope, employers.data ?? [])}
            </option>
          ))}
        </Select>
      </div>
      {chosen !== undefined && (
        <RepositoryEmployerBar
          key={`${chosen.ref}-${employerKey(chosen.employer_ref)}`}
          scope={chosen}
        />
      )}
    </div>
  );
}
