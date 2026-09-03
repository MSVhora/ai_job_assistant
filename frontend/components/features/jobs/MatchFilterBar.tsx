"use client";

import type { MatchFilterValues } from "@/hooks/use-matches";

export const selectStyles =
  "w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100";

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

const SORT_OPTIONS = [
  { value: "final_score", label: "Best match" },
  { value: "vector_score", label: "Similarity" },
  { value: "posted_at", label: "Newest" },
];

export function MatchFilterBar({
  filters,
  onChange,
}: {
  filters: MatchFilterValues;
  onChange: (filters: MatchFilterValues) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="flex flex-col gap-1">
        <label htmlFor="match-location" className="text-xs font-medium text-gray-700 dark:text-gray-300">
          Location
        </label>
        <input
          id="match-location"
          type="text"
          value={filters.location ?? ""}
          onChange={(event) =>
            onChange({ ...filters, location: event.target.value.trim() || undefined })
          }
          placeholder="e.g. Berlin"
          className={`${selectStyles} w-40`}
        />
      </div>
      <SelectField
        id="match-remote"
        label="Workplace"
        value={filters.remote_type ?? ""}
        options={REMOTE_OPTIONS}
        onChange={(value) =>
          onChange({ ...filters, remote_type: (value || undefined) as MatchFilterValues["remote_type"] })
        }
      />
      <SelectField
        id="match-job-type"
        label="Job type"
        value={filters.job_type ?? ""}
        options={JOB_TYPE_OPTIONS}
        onChange={(value) =>
          onChange({ ...filters, job_type: (value || undefined) as MatchFilterValues["job_type"] })
        }
      />
      <SelectField
        id="match-recency"
        label="Posted"
        value={filters.posted_within_days !== undefined ? String(filters.posted_within_days) : ""}
        options={RECENCY_OPTIONS}
        onChange={(value) =>
          onChange({ ...filters, posted_within_days: value ? Number(value) : undefined })
        }
      />
      <SelectField
        id="match-sort"
        label="Sort"
        value={filters.sort ?? "final_score"}
        options={SORT_OPTIONS}
        onChange={(value) => onChange({ ...filters, sort: value as MatchFilterValues["sort"] })}
      />
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
      <label htmlFor={id} className="text-xs font-medium text-gray-700 dark:text-gray-300">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${selectStyles} w-36`}
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
