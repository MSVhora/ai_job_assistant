"use client";

import { Select } from "@/components/ui/select";
import { IMPACT_LABELS } from "@/lib/achievement-view";

import type { MetricFilter } from "./review-tabs";

export function ImpactFilters({
  impact,
  metric,
  onImpact,
  onMetric,
}: {
  impact: string;
  metric: MetricFilter;
  onImpact: (impact: string) => void;
  onMetric: (metric: MetricFilter) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2">
        <label htmlFor="achievement-impact" className="text-sm text-gray-700">
          Impact
        </label>
        <Select
          id="achievement-impact"
          value={impact}
          className="w-44"
          onChange={(event) => {
            onImpact(event.target.value);
          }}
        >
          <option value="">Any impact</option>
          {Object.entries(IMPACT_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      <div className="flex items-center gap-2">
        <label htmlFor="achievement-metric" className="text-sm text-gray-700">
          Metric
        </label>
        <Select
          id="achievement-metric"
          value={metric}
          className="w-52"
          onChange={(event) => {
            onMetric(event.target.value as MetricFilter);
          }}
        >
          <option value="">Any</option>
          <option value="yes">Has a confirmed metric</option>
          <option value="no">No confirmed metric</option>
        </Select>
      </div>
    </div>
  );
}
