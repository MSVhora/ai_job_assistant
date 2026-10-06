"use client";

import type { AtsKeywordHit } from "@/lib/api";
import { SectionCard } from "@/components/features/ats/AtsReportShared";

const KEYWORD_PRIORITY_LABEL: Record<string, { label: string; style: string }> = {
  critical: { label: "Critical", style: "bg-red-50 text-red-700 border-red-200" },
  important: { label: "Important", style: "bg-amber-50 text-amber-700 border-amber-200" },
  nice_to_have: { label: "Nice to have", style: "bg-gray-50 text-gray-600 border-gray-200" },
};

function HitChip({ hit, tone }: { hit: AtsKeywordHit; tone: "matched" | "missing" }) {
  const matched = tone === "matched";
  const priority = KEYWORD_PRIORITY_LABEL[hit.priority] ?? KEYWORD_PRIORITY_LABEL.nice_to_have;
  return (
    <li
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${
        matched
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : `${priority.style} ${hit.priority === "critical" ? "font-semibold" : ""}`
      }`}
      title={priority.label}
    >
      {hit.keyword}
      {matched && (
        <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3 w-3">
          <path
            fillRule="evenodd"
            d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.8 3.8 6.8-6.8a1 1 0 011.4 0z"
            clipRule="evenodd"
          />
        </svg>
      )}
    </li>
  );
}

function KeywordColumn({
  tone,
  title,
  hits,
}: {
  tone: "matched" | "missing";
  title: string;
  hits: AtsKeywordHit[];
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl bg-gray-50/70 p-4">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-2 text-sm font-semibold text-gray-900">{title}</p>
        <span className="text-xs font-semibold text-gray-500">{hits.length} found</span>
      </div>
      {hits.length === 0 ? (
        <p className="text-sm text-gray-500">None detected.</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {hits.map((hit) => (
            <HitChip key={hit.keyword} hit={hit} tone={tone} />
          ))}
        </ul>
      )}
    </div>
  );
}

export function AtsKeywordsPanel({
  matched,
  missing,
}: {
  matched: AtsKeywordHit[];
  missing: AtsKeywordHit[];
}) {
  return (
    <SectionCard
      title="Keyword match"
      count={matched.length + missing.length}
      icon={
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true" className="h-5 w-5">
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="M15.5 15.5L21 21" strokeLinecap="round" />
        </svg>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <KeywordColumn tone="matched" title="Matched keywords" hits={matched} />
        <KeywordColumn tone="missing" title="Missing keywords" hits={missing} />
      </div>
      {missing.length > 0 && (
        <p className="text-xs text-gray-500">
          Hover a missing keyword chip to see how the ATS weights it. Critical and important
          gaps cost the most points.
        </p>
      )}
    </SectionCard>
  );
}
