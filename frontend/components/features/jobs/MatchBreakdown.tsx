import type { MatchResponse } from "@/lib/api";
import { scorePercent } from "@/lib/salary";

import { ScoreRow } from "./job-detail-parts";
import { SparkleIcon } from "./match-card-parts";

export function MatchBreakdown({ match }: { match: MatchResponse }) {
  return (
    <div className="rounded-2xl border border-violet-100 bg-violet-50/50 p-4">
      <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-violet-700 uppercase">
        <SparkleIcon />
        AI match breakdown
      </h4>
      <div className="flex flex-col gap-1.5">
        <ScoreRow label="Final score" value={scorePercent(match.final_score)} />
        <ScoreRow label="Similarity" value={scorePercent(match.vector_score ?? 0)} />
        {match.role_fit != null && <ScoreRow label="Role fit" value={`${match.role_fit}/10`} />}
        {match.company_fit != null && (
          <ScoreRow label="Company fit" value={`${match.company_fit}/10`} />
        )}
      </div>
      {match.rationale && (
        <p className="mt-3 rounded-xl border border-violet-100 bg-white px-3 py-2.5 text-sm leading-relaxed text-gray-700">
          {match.rationale}
        </p>
      )}
    </div>
  );
}
