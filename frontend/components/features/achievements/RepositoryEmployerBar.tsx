"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useEmployers, useUpdateScopes } from "@/hooks/use-evidence-sync";
import type { EvidenceScope } from "@/lib/api";
import { findOption, optionKey, optionRef } from "@/lib/employer-options";
import { employerKey } from "@/lib/evidence-progress";

/** Maps a repository to an employer; every achievement from it follows, except your own choices. */
export function RepositoryEmployerBar({ scope }: { scope: EvidenceScope }) {
  const employers = useEmployers();
  const update = useUpdateScopes();
  const saved = employerKey(scope.employer_ref);
  const [value, setValue] = useState(saved);
  const options = employers.data ?? [];

  const apply = () => {
    const chosen = findOption(options, value);
    update.mutate(
      {
        scopes: [{ ref: scope.ref, employer_ref: chosen === undefined ? null : optionRef(chosen) }],
        acknowledged: false,
      },
      {
        onSuccess: () => {
          toast.success(`Employer set for ${scope.ref}`);
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-violet-200 bg-violet-50/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="repository-employer" className="text-sm font-semibold text-gray-800">
          Employer for {scope.ref}
        </label>
        <Select
          id="repository-employer"
          value={value}
          disabled={employers.isPending || update.isPending}
          className="w-64"
          onChange={(event) => {
            setValue(event.target.value);
          }}
        >
          <option value="">Not mapped (treated as a project)</option>
          {options.map((option) => (
            <option key={optionKey(option)} value={optionKey(option)}>
              {option.label}
            </option>
          ))}
        </Select>
        <Button disabled={update.isPending || value === saved} onClick={apply}>
          {update.isPending ? "Applying…" : "Apply to this repository"}
        </Button>
      </div>
      <p className="text-xs text-gray-600">
        Sets the employer of every achievement from this repository. Achievements whose employer you
        chose individually keep it.
      </p>
    </div>
  );
}
