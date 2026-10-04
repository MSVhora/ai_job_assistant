"use client";

import { Select } from "@/components/ui/select";
import { useGithubScopes } from "@/hooks/use-evidence-sync";
import { employerKey } from "@/lib/evidence-progress";

import { RepositoryEmployerBar } from "./RepositoryEmployerBar";

export function RepositoryFilter({
  value,
  onChange,
}: {
  value: string;
  onChange: (repository: string) => void;
}) {
  const scopes = useGithubScopes(true);
  const repositories = (scopes.data ?? [])
    .filter((scope) => scope.enabled || scope.last_synced_at !== null)
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
          className="w-64"
          onChange={(event) => {
            onChange(event.target.value);
          }}
        >
          <option value="">All repositories</option>
          {repositories.map((scope) => (
            <option key={scope.ref} value={scope.ref}>
              {scope.ref}
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
