"use client";

import { DEFAULT_MATCH_FILTERS, type MatchFilterValues } from "@/hooks/use-matches";
import type { PrioritySetting } from "@/hooks/use-priority-setting";
import { Input } from "@/components/ui/input";

import { PrioritySlider } from "./PrioritySlider";

export const selectStyles =
  "w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500";

const REMOTE_OPTIONS = [
  { value: "", label: "Any workplace" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "on_site", label: "On-site" },
];

const JOB_TYPE_OPTIONS = [
  { value: "", label: "Any job type" },
  { value: "full_time", label: "Full-time" },
  { value: "part_time", label: "Part-time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
  { value: "temporary", label: "Temporary" },
];

const RECENCY_OPTIONS = [
  { value: "", label: "Any date" },
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
];

export const SORT_OPTIONS = [
  { value: "final_score", label: "Best match" },
  { value: "vector_score", label: "Similarity" },
  { value: "posted_at", label: "Newest" },
];

export function hasActiveFilters(filters: MatchFilterValues): boolean {
  return (
    filters.location !== undefined &&
    filters.location !== "" ||
    filters.remote_type !== undefined ||
    filters.job_type !== undefined ||
    filters.posted_within_days !== undefined
  );
}

function activeFilterCount(filters: MatchFilterValues): number {
  return (
    (filters.location !== undefined && filters.location !== "" ? 1 : 0) +
    (filters.remote_type !== undefined ? 1 : 0) +
    (filters.job_type !== undefined ? 1 : 0) +
    (filters.posted_within_days !== undefined ? 1 : 0)
  );
}

export function MatchFilterPanel({
  filters,
  onChange,
  priority,
}: {
  filters: MatchFilterValues;
  onChange: (filters: MatchFilterValues) => void;
  priority: PrioritySetting;
}) {
  const active = activeFilterCount(filters);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label
          htmlFor="filter-location"
          className="text-xs font-semibold uppercase tracking-wide text-gray-500"
        >
          Location
        </label>
        <Input
          id="filter-location"
          value={filters.location ?? ""}
          onChange={(event) =>
            onChange({ ...filters, location: event.target.value || undefined })
          }
          placeholder="Bangalore"
        />
      </div>
      <SelectField
        id="filter-remote"
        label="Workplace"
        value={filters.remote_type ?? ""}
        options={REMOTE_OPTIONS}
        onChange={(value) =>
          onChange({
            ...filters,
            remote_type: (value || undefined) as MatchFilterValues["remote_type"],
          })
        }
      />
      <SelectField
        id="filter-job-type"
        label="Job type"
        value={filters.job_type ?? ""}
        options={JOB_TYPE_OPTIONS}
        onChange={(value) =>
          onChange({
            ...filters,
            job_type: (value || undefined) as MatchFilterValues["job_type"],
          })
        }
      />
      <SelectField
        id="filter-recency"
        label="Posted"
        value={
          filters.posted_within_days !== undefined ? String(filters.posted_within_days) : ""
        }
        options={RECENCY_OPTIONS}
        onChange={(value) =>
          onChange({ ...filters, posted_within_days: value ? Number(value) : undefined })
        }
      />
      <SelectField
        id="filter-sort"
        label="Sort by"
        value={filters.sort ?? "final_score"}
        options={SORT_OPTIONS}
        onChange={(value) => onChange({ ...filters, sort: value as MatchFilterValues["sort"] })}
      />
      <div className="border-t border-gray-100 pt-3">
        <PrioritySlider
          value={priority.value ?? 2 / 3}
          onChange={priority.change}
          disabled={priority.disabled}
        />
      </div>
      {active > 0 && (
        <button
          type="button"
          onClick={() =>
            onChange({ ...DEFAULT_MATCH_FILTERS, location: undefined })
          }
          className="w-fit rounded-full border border-violet-300 bg-white px-4 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Clear filters ({active})
        </button>
      )}
    </div>
  );
}

function SelectField({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className="text-xs font-semibold uppercase tracking-wide text-gray-500"
      >
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={selectStyles}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
