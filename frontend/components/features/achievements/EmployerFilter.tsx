"use client";

import { Select } from "@/components/ui/select";
import type { EmployerGroup } from "@/lib/api";
import { employerChoice } from "@/lib/draft-groups";

export function EmployerFilter({
  groups,
  value,
  onChange,
}: {
  groups: EmployerGroup[];
  value: string;
  onChange: (choice: string) => void;
}) {
  if (groups.length === 0) return null;
  const total = groups.reduce((sum, group) => sum + group.total, 0);
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="achievement-employer" className="text-sm text-gray-700">
        Employer
      </label>
      <Select
        id="achievement-employer"
        value={value}
        className="w-72 max-w-full"
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        <option value="">All employers ({total})</option>
        {groups.map((group) => (
          <option key={employerChoice(group)} value={employerChoice(group)}>
            {group.label} ({group.total})
          </option>
        ))}
      </Select>
    </div>
  );
}
