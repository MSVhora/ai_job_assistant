"use client";

import type { SourceInfo } from "@/lib/api";
import { useFormContext, useWatch } from "react-hook-form";

import { POSTED_WITHIN_OPTIONS, type SearchFormValues } from "./search-form-schema";

function optionDisplay(value: string | boolean | undefined, type: string): string | null {
  if (value === undefined) return null;
  if (type === "boolean") return value === true ? "On" : null;
  if (typeof value === "string" && value.trim() === "") return null;
  return String(value);
}

interface ReviewRow {
  label: string;
  value: string;
}

export function ReviewSummary({
  source,
  profileName,
  currency,
}: {
  source: SourceInfo;
  profileName: string | null;
  currency: string | null;
}) {
  const { control } = useFormContext<SearchFormValues>();
  const values = useWatch({ control });
  const query = values.query ?? {};
  const title = query.title?.trim();
  const skillsAll = query.skills_all?.trim();
  const skills = query.skills?.trim();
  const exclude = source.supports_exclusions ? (query.exclude?.trim() ?? "") : null;
  const postedWithin =
    POSTED_WITHIN_OPTIONS.find((option) => option.value === values.posted_within)?.label ?? "—";
  const advanced = (source.filters ?? [])
    .map((decl) => ({
      label: decl.label,
      display: optionDisplay(query.options?.[decl.key], decl.type),
    }))
    .filter((entry): entry is { label: string; display: string } => entry.display !== null);

  const rows: ReviewRow[] = [
    { label: "Profile", value: profileName ?? "—" },
    { label: "Source", value: source.name },
    { label: "Search title", value: title === undefined || title === "" ? "—" : title },
    {
      label: "Must-have skills",
      value: skillsAll === undefined || skillsAll === "" ? "—" : skillsAll,
    },
    { label: "Include skills", value: skills === undefined || skills === "" ? "—" : skills },
    {
      label: "Exclude skills",
      value: exclude === null ? "not supported by this source" : exclude === "" ? "—" : exclude,
    },
    {
      label: "Location",
      value: (values.location ?? "").trim() === "" ? "—" : (values.location ?? "").trim(),
    },
    {
      label: "Country",
      value: (values.country ?? "").trim() === "" ? "—" : (values.country ?? "").trim(),
    },
    { label: "Posted within", value: postedWithin },
    {
      label: "Min. salary",
      value:
        (values.minSalary ?? "").trim() === ""
          ? "—"
          : `${values.minSalary}${currency !== null ? ` ${currency}` : ""}`,
    },
    {
      label: "Max. salary",
      value:
        (values.maxSalary ?? "").trim() === ""
          ? "—"
          : `${values.maxSalary}${currency !== null ? ` ${currency}` : ""}`,
    },
    { label: "Results wanted", value: String(values.results_wanted ?? "—") },
    {
      label: "Advanced filters",
      value:
        advanced.length === 0
          ? "none"
          : advanced.map((entry) => `${entry.label}: ${entry.display}`).join(", "),
    },
  ];

  return (
    <section aria-label="Review of the search you are about to start">
      <h3 className="text-sm font-bold tracking-tight text-gray-900">Review</h3>
      <dl className="mt-2 flex flex-col rounded-2xl border border-violet-100 bg-violet-50/50 p-3.5">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between gap-4 border-b border-violet-100/70 py-1.5 text-sm last:border-0 last:pb-0"
          >
            <dt className="shrink-0 text-xs font-semibold tracking-wide text-gray-500 uppercase">
              {row.label}
            </dt>
            <dd className="min-w-0 text-right break-words text-gray-900">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
