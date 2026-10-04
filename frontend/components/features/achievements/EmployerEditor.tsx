"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { useEditAchievement } from "@/hooks/use-achievements";
import { useEmployers, useGithubScopes } from "@/hooks/use-evidence-sync";
import type { Achievement } from "@/lib/api";
import { employerSource } from "@/lib/achievement-view";
import { findOption, optionKey, optionRef } from "@/lib/employer-options";
import { employerKey, employerLabel } from "@/lib/evidence-progress";

const FOLLOW = "";

/** Chooses who this achievement is attributed to; it outranks the repository's employer. */
export function EmployerEditor({ achievement }: { achievement: Achievement }) {
  const edit = useEditAchievement();
  const employers = useEmployers();
  const scopes = useGithubScopes(achievement.project_key !== null);
  const saved =
    employerSource(achievement.employer_ref) === "user"
      ? employerKey(achievement.employer_ref)
      : FOLLOW;
  const [value, setValue] = useState(saved);
  const options = employers.data ?? [];
  const repository = scopes.data?.find((scope) => scope.ref === achievement.project_key);
  const repositoryEmployer = employerLabel(repository?.employer_ref);

  const save = () => {
    const chosen = findOption(options, value);
    edit.mutate(
      {
        id: achievement.id,
        payload: {
          employer_ref: value === FOLLOW || chosen === undefined ? null : optionRef(chosen),
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
        <Select
          id="achievement-employer"
          value={value}
          disabled={employers.isPending}
          onChange={(event) => {
            setValue(event.target.value);
          }}
        >
          <option value={FOLLOW}>
            {achievement.project_key === null
              ? "Not set"
              : `Same as repository (${repositoryEmployer ?? "not mapped"})`}
          </option>
          {options.map((option) => (
            <option key={optionKey(option)} value={optionKey(option)}>
              {option.label}
            </option>
          ))}
        </Select>
      </Field>
      <div>
        <Button disabled={edit.isPending || value === saved} onClick={save}>
          Save employer
        </Button>
      </div>
    </div>
  );
}
