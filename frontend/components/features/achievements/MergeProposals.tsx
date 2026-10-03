"use client";

import { useMergeProposals } from "@/hooks/use-achievements";

import type { MergeCandidate } from "./MergeDialog";

export function MergeProposals({ onMerge }: { onMerge: (pair: MergeCandidate[]) => void }) {
  const proposals = useMergeProposals();
  if (!proposals.isSuccess || proposals.data.length === 0) return null;
  return (
    <details className="rounded-2xl border border-violet-200 bg-violet-50/60 p-4">
      <summary className="cursor-pointer text-sm font-semibold text-violet-900">
        {proposals.data.length} possible duplicate{proposals.data.length === 1 ? "" : "s"}
      </summary>
      <p className="mt-2 text-xs text-gray-600">
        Similar achievements from the same repository and period. Nothing is merged unless you
        choose to.
      </p>
      <ul className="mt-2 flex flex-col gap-2">
        {proposals.data.map((proposal) => (
          <li
            key={`${proposal.first_id}-${proposal.second_id}`}
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white p-3 text-sm"
          >
            <span>
              {proposal.first_title} <span className="text-gray-400">≈</span>{" "}
              {proposal.second_title}{" "}
              <span className="text-xs text-gray-500">
                ({Math.round(proposal.similarity * 100)}% similar)
              </span>
            </span>
            <button
              type="button"
              className="rounded-full border border-violet-300 px-3 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-50"
              onClick={() => {
                onMerge([
                  { id: proposal.first_id, title: proposal.first_title },
                  { id: proposal.second_id, title: proposal.second_title },
                ]);
              }}
            >
              Review merge
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
