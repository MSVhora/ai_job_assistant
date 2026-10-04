import type { EmployerOption } from "@/lib/api";

/** Select value for an employer option: stable across reloads, matches `employerKey` of a stored ref. */
export function optionKey(option: EmployerOption): string {
  return option.kind === "personal"
    ? "personal"
    : `${option.company ?? ""}|${option.start_date ?? ""}`;
}

/** The `employer_ref` the API expects for an option. */
export function optionRef(option: EmployerOption): Record<string, unknown> {
  return option.kind === "personal"
    ? { kind: "personal" }
    : { company: option.company, start_date: option.start_date };
}

export function findOption(options: EmployerOption[], key: string): EmployerOption | undefined {
  return options.find((option) => optionKey(option) === key);
}
