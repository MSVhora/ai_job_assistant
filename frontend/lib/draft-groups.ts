import type { EmployerGroup } from "@/lib/api";

/** "" is every employer; otherwise "personal", "unassigned" or "employer:<company>". */
export function employerChoice(group: EmployerGroup): string {
  return group.kind === "employer" ? `employer:${group.label}` : group.kind;
}

export function employerParams(choice: string): {
  employer?: string;
  employer_kind?: "personal" | "unassigned";
} {
  if (choice === "personal" || choice === "unassigned") return { employer_kind: choice };
  if (choice.startsWith("employer:")) return { employer: choice.slice("employer:".length) };
  return {};
}

export function choiceLabel(groups: EmployerGroup[], choice: string): string {
  return groups.find((group) => employerChoice(group) === choice)?.label ?? "all employers";
}

/** Ids of the drafts in the current employer/repository view, and the clean subset of them. */
export function viewIds(
  groups: EmployerGroup[],
  choice: string,
  repository: string,
): { drafts: string[]; eligible: string[] } {
  const repositories = groups
    .filter((group) => choice === "" || employerChoice(group) === choice)
    .flatMap((group) => group.repositories)
    .filter((repo) => repository === "" || repo.project_key === repository);
  return {
    drafts: repositories.flatMap((repo) => repo.draft_ids),
    eligible: repositories.flatMap((repo) => repo.eligible_ids),
  };
}

/** Repositories that have drafts under the chosen employer; undefined means no restriction. */
export function employerRepositories(
  groups: EmployerGroup[],
  choice: string,
): ReadonlySet<string> | undefined {
  if (choice === "") return undefined;
  return new Set(
    groups
      .filter((group) => employerChoice(group) === choice)
      .flatMap((group) => group.repositories)
      .flatMap((repo) => (repo.project_key === null ? [] : [repo.project_key])),
  );
}
