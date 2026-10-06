"use client";

import { AtsCategoryGrid } from "@/components/features/ats/AtsCategoryGrid";
import { AtsInsights } from "@/components/features/ats/AtsInsights";
import { AtsKeywordsPanel } from "@/components/features/ats/AtsKeywordsPanel";
import { AtsReportHero } from "@/components/features/ats/AtsReportHero";
import { AtsSuggestions } from "@/components/features/ats/AtsSuggestions";
import type { AtsScoreResponse } from "@/lib/api";

export function AtsReport({ report, onReset }: { report: AtsScoreResponse; onReset: () => void }) {
  return (
    <div className="flex flex-col gap-7" aria-live="polite">
      <AtsReportHero report={report} onReset={onReset} />
      <AtsCategoryGrid categories={report.categories} />
      <AtsInsights strengths={report.strengths} gaps={report.gaps} />
      <AtsKeywordsPanel matched={report.matched_keywords} missing={report.missing_keywords} />
      <AtsSuggestions suggestions={report.suggestions} />
      <p className="text-center text-xs text-gray-400">
        AI-generated ATS estimate — scores reflect parsed text, not how a human recruiter reads your resume.
      </p>
    </div>
  );
}
