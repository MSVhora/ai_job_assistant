import type { EmployerOption } from "@/lib/api";

export const PERSONAL_KEY = "personal";

/** Select value for an employer: its group key, or "personal". Empty means "none chosen". */
export function optionKey(option: EmployerOption): string {
  return option.kind === "personal" ? PERSONAL_KEY : option.key;
}

/** The `employer_ref` the API expects: company-level, never a single experience entry. */
export function optionRef(option: EmployerOption): Record<string, unknown> {
  return option.kind === "personal" ? { kind: "personal" } : { company: option.company };
}

export function findOption(options: EmployerOption[], key: string): EmployerOption | undefined {
  return options.find((option) => optionKey(option) === key);
}

/** The employer a stored reference belongs to: personal, or the group that has its company name. */
export function findOptionForRef(
  options: EmployerOption[],
  ref: Record<string, unknown> | null | undefined,
): EmployerOption | undefined {
  if (ref === null || ref === undefined) return undefined;
  if (ref.kind === "personal") return options.find((option) => option.kind === "personal");
  const company = typeof ref.company === "string" ? ref.company.trim().toLowerCase() : "";
  if (company === "") return undefined;
  return options.find((option) =>
    (option.aliases ?? []).some((alias) => alias.trim().toLowerCase() === company),
  );
}

/** Select value for a stored reference, "" when it matches no employer. */
export function keyForRef(
  options: EmployerOption[],
  ref: Record<string, unknown> | null | undefined,
): string {
  const option = findOptionForRef(options, ref);
  return option === undefined ? "" : optionKey(option);
}
