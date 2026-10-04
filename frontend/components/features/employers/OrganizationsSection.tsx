"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useOwners, useSetOwnerEmployer } from "@/hooks/use-employers";
import { useGithubScopes } from "@/hooks/use-evidence-sync";
import type { EmployerOption, EvidenceScope, OwnerSummary } from "@/lib/api";
import { findOption, keyForRef, optionRef } from "@/lib/employer-options";

import { EmployerSelect } from "./EmployerSelect";

function ownerOf(ref: string): string {
  return ref.split("/")[0]?.toLowerCase() ?? "";
}

function OrganizationRow({
  owner,
  options,
  scopes,
}: {
  owner: OwnerSummary;
  options: EmployerOption[];
  scopes: EvidenceScope[];
}) {
  const set = useSetOwnerEmployer();
  const saved = keyForRef(options, owner.employer);
  const [chosen, setChosen] = useState<string | null>(null);
  const value = chosen ?? saved;
  const own = scopes.filter((scope) => ownerOf(scope.ref) === owner.owner);
  const keeps = own.filter((scope) => scope.employer_ref?.source === "user").length;
  const changes = own.length - keeps;

  const apply = () => {
    const match = findOption(options, value);
    set.mutate(
      { owner: owner.owner, employerRef: match === undefined ? null : optionRef(match) },
      {
        onSuccess: () => {
          setChosen(null);
          toast.success(`Employer set for ${owner.owner}`);
        },
      },
    );
  };

  return (
    <li className="flex flex-col gap-2 rounded-xl border border-gray-200 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-gray-900">{owner.owner}</span>
        <span className="text-xs text-gray-600">
          {owner.selected} of {owner.repos} selected
        </span>
        {owner.personal_account && <Badge>Your account</Badge>}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <EmployerSelect
            ariaLabel={`Employer for organization ${owner.owner}`}
            value={value}
            options={options}
            noneLabel="No employer"
            disabled={set.isPending}
            className="w-56"
            onChange={setChosen}
          />
          <Button
            aria-label={`Apply employer to ${owner.owner}`}
            disabled={set.isPending || value === saved}
            onClick={apply}
          >
            {set.isPending ? "Applying…" : "Apply"}
          </Button>
        </div>
      </div>
      {value !== saved && (
        <p className="text-xs text-gray-600">
          {changes} {changes === 1 ? "repository changes" : "repositories change"}, selected or not;{" "}
          {keeps} keep{keeps === 1 ? "s" : ""} the employer you set on it.
        </p>
      )}
      {set.isError && (
        <p role="alert" className="text-xs text-red-700">
          Could not apply: {set.error.message}
        </p>
      )}
    </li>
  );
}

/** Maps a GitHub owner to an employer; its repositories without their own mapping follow. */
export function OrganizationsSection({ options }: { options: EmployerOption[] }) {
  const owners = useOwners(true);
  const scopes = useGithubScopes(true);
  const rows = owners.data ?? [];
  if (rows.length === 0) return null;
  return (
    <section className="mt-5" aria-label="Organizations">
      <h3 className="text-sm font-bold text-gray-900">Organizations</h3>
      <p className="mb-2 text-xs text-gray-600">
        Map a GitHub organization to an employer once: all its repositories, including ones you have
        not selected, use it unless you mapped a repository yourself.
      </p>
      <ul className="flex flex-col gap-2" aria-label="Organizations">
        {rows.map((owner) => (
          <OrganizationRow
            key={owner.owner}
            owner={owner}
            options={options}
            scopes={scopes.data ?? []}
          />
        ))}
      </ul>
    </section>
  );
}
