"use client";

import Link from "next/link";

import { Card } from "@/components/ui/card";
import type { ResumeGap } from "@/lib/api";

export function GapsPanel({ gaps }: { gaps: ResumeGap[] }) {
  if (gaps.length === 0) return null;
  return (
    <Card
      title={
        <h2 className="text-lg font-semibold text-gray-900">Not supported by your evidence</h2>
      }
    >
      <p className="mb-3 text-xs text-gray-600">
        The job description asks for these, but nothing you have approved supports them, so they are
        not claimed.
      </p>
      <ul className="flex flex-col gap-2">
        {gaps.map((gap) => (
          <li key={gap.requirement} className="flex flex-col gap-1 rounded-xl bg-gray-50 p-3">
            <p className="text-sm font-semibold text-gray-900">{gap.requirement}</p>
            {gap.nearest_evidence ? (
              <p className="text-xs text-gray-600">Nearest evidence: {gap.nearest_evidence}</p>
            ) : null}
            <Link
              href="/evidence"
              className="self-start text-xs font-semibold text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
            >
              Add a note
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
