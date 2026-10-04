"use client";

import { useState } from "react";
import { toast } from "sonner";

import { EmployerSelect } from "@/components/features/employers/EmployerSelect";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { useEditAchievement } from "@/hooks/use-achievements";
import { useEmployers, useGithubScopes } from "@/hooks/use-evidence-sync";
import type { Achievement } from "@/lib/api";
import { employerSource } from "@/lib/achievement-view";
import { findOption, keyForRef, optionRef } from "@/lib/employer-options";
import { employerLabel } from "@/lib/evidence-progress";

const FOLLOW = "";

/** Chooses who this achievement is attributed to; it outranks the repository's employer. */
export function EmployerEditor({ achievement }: { achievement: Achievement }) {
  const edit = useEditAchievement();
  const employers = useEmployers();
  const scopes = useGithubScopes(achievement.project_key !== null);
  const options = employers.data ?? [];
  const saved =
    employerSource(achievement.employer_ref) === "user"
      ? keyForRef(options, achievement.employer_ref)
      : FOLLOW;
  const [chosen, setChosen] = useState<string | null>(null);
  const value = chosen ?? saved;
  const repository = scopes.data?.find((scope) => scope.ref === achievement.project_key);
  const repositoryEmployer = employerLabel(repository?.employer_ref);

  const save = () => {
    const option = findOption(options, value);
    edit.mutate(
      {
        id: achievement.id,
        payload: {
          employer_ref: value === FOLLOW || option === undefined ? null : optionRef(option),
        },
      },
      {
        onSuccess: () => {
          toast.success("Employer saved");
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-2">
      <Field
        label="Employer"
        htmlFor="achievement-employer"
        hint="Decides which company's section this lands under on a resume. A choice here outranks the repository's employer; “Same as repository” follows it again."
      >
        <EmployerSelect
          id="achievement-employer"
          value={value}
          options={options}
          noneLabel={
            achievement.project_key === null
              ? "Not set"
              : `Same as repository (${repositoryEmployer ?? "not mapped"})`
          }
          disabled={employers.isPending}
          onChange={setChosen}
        />
      </Field>
      <div>
        <Button disabled={edit.isPending || value === saved} onClick={save}>
          Save employer
        </Button>
      </div>
    </div>
  );
}
