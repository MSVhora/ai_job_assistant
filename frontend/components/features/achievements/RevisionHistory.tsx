"use client";

import { useRevisions } from "@/hooks/use-achievements";
import { formatRevisionDiff } from "@/lib/achievement-view";

const SOURCE_LABELS: Record<string, string> = {
  ai_extraction: "Created by extraction",
  manual_edit: "Edited",
  merge: "Merged",
  split_: "Split",
  split: "Split",
  metric_confirmation: "Metric confirmed",
  status_change: "Status change",
};

export function RevisionHistory({ achievementId }: { achievementId: string }) {
  const revisions = useRevisions(achievementId);
  if (revisions.isPending) return <p className="text-sm text-gray-500">Loading history…</p>;
  if (revisions.isError)
    return <p className="text-sm text-red-700">History could not be loaded.</p>;
  if (revisions.data.length === 0) {
    return <p className="text-sm text-gray-500">No changes recorded yet.</p>;
  }
  return (
    <ol className="flex flex-col gap-2" aria-label="Revision history">
      {revisions.data.map((revision) => (
        <li key={revision.id} className="rounded-xl border border-gray-200 p-3 text-xs">
          <p className="font-semibold text-gray-900">
            {SOURCE_LABELS[revision.source] ?? revision.source}
            <span className="ml-2 font-normal text-gray-500">
              {new Date(revision.created_at).toLocaleString()}
            </span>
          </p>
          <ul className="mt-1 text-gray-600">
            {formatRevisionDiff(revision.diff).map((line) => (
              <li key={line} className="break-words">
                {line}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
