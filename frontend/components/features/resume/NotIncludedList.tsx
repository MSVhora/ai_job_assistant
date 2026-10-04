"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApproveBullet, usePinBullet, useWriteAchievement } from "@/hooks/use-resume-documents";
import { REASON_LABELS, type NotIncludedRow } from "@/lib/resume-view";

const ACTION =
  "rounded-full border border-violet-300 px-3 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:opacity-50";

export function NotIncludedList({
  documentId,
  rows,
}: {
  documentId: string;
  rows: NotIncludedRow[];
}) {
  const pin = usePinBullet(documentId);
  const approve = useApproveBullet(documentId);
  const write = useWriteAchievement(documentId);
  const busy = pin.isPending || approve.isPending || write.isPending;

  if (rows.length === 0) return null;
  return (
    <Card title={<h2 className="text-lg font-semibold text-gray-900">Not included</h2>}>
      <p className="mb-3 text-xs text-gray-600">
        Ranked by priority. Adding something re-fits the page; a bullet is only kept if it fits.
      </p>
      <ol aria-label="Not included" className="flex flex-col gap-2" aria-live="polite">
        {rows.map((row) => (
          <li
            key={`${row.kind}-${row.id}`}
            className="flex flex-col gap-1.5 rounded-xl border border-gray-100 p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={row.reason === "needs_review" ? "warn" : "neutral"}>
                {REASON_LABELS[row.reason]}
              </Badge>
              <span className="text-xs text-gray-500">
                priority {Math.round(row.priority * 100)}
              </span>
              {row.context && <span className="text-xs text-gray-500">{row.context}</span>}
            </div>
            <p className="text-sm text-gray-900 select-text">{row.label}</p>
            {row.flags.length > 0 && (
              <p className="text-xs text-amber-800">Flagged: {row.flags.join("; ")}</p>
            )}
            <div className="flex gap-2">
              {row.reason === "did_not_fit" && (
                <button
                  type="button"
                  className={ACTION}
                  disabled={busy}
                  onClick={() => {
                    pin.mutate({ bulletId: row.id, pinned: true });
                  }}
                >
                  Add
                </button>
              )}
              {row.reason === "needs_review" && (
                <button
                  type="button"
                  className={ACTION}
                  disabled={busy}
                  onClick={() => {
                    approve.mutate(row.id);
                  }}
                >
                  Approve anyway
                </button>
              )}
              {row.reason === "not_written" && (
                <button
                  type="button"
                  className={ACTION}
                  disabled={busy}
                  onClick={() => {
                    write.mutate(row.id);
                  }}
                >
                  Write and add
                </button>
              )}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
