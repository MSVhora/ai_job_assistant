"use client";

import { SectionCard } from "@/components/features/ats/AtsReportShared";

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4 shrink-0">
      <path
        fillRule="evenodd"
        d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.8 3.8 6.8-6.8a1 1 0 011.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4 shrink-0">
      <path
        fillRule="evenodd"
        d="M8.49 2.09a1 1 0 011.02 0l7 4A1 1 0 0117 7v6a1 1 0 01-.49.86l-7 4a1 1 0 01-.98 0l-7-4A1 1 0 011 13V7a1 1 0 01.49-.86l7-4zM10 6a1 1 0 011 1v3a1 1 0 11-2 0V7a1 1 0 011-1zm0 6.5a1 1 0 100 2 1 1 0 000-2z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function AtsInsights({ strengths, gaps }: { strengths: string[]; gaps: string[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <SectionCard
        title="Strengths"
        accent="emerald"
        count={strengths.length}
        icon={<CheckIcon />}
      >
        <ul className="flex flex-col gap-2.5">
          {strengths.map((strength) => (
            <li key={strength} className="flex items-start gap-2 text-sm text-gray-700">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                <CheckIcon />
              </span>
              {strength}
            </li>
          ))}
        </ul>
      </SectionCard>
      <SectionCard title="Gaps" accent="amber" count={gaps.length} icon={<AlertIcon />}>
        <ul className="flex flex-col gap-2.5">
          {gaps.map((gap) => (
            <li key={gap} className="flex items-start gap-2 text-sm text-gray-700">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                <AlertIcon />
              </span>
              {gap}
            </li>
          ))}
        </ul>
      </SectionCard>
    </div>
  );
}
