"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { isRebuildActive, useMatchRebuildStatus, useStartMatchRebuild } from "@/hooks/use-match-rebuild";

const STATUS_LABELS: Record<string, string> = {
  idle: "Never rebuilt",
  pending: "Rebuild queued…",
  running: "Re-scoring matches…",
  succeeded: "Matches rebuilt",
  failed: "Rebuild failed",
};

function RebuildTrigger({ profileId, disabled }: { profileId: string; disabled: boolean }) {
  const start = useStartMatchRebuild();
  const alreadyDisabled = disabled || start.isPending;
  return (
    <button
      type="button"
      disabled={alreadyDisabled}
      onClick={() => start.mutate(profileId)}
      className="shrink-0 rounded-xl border border-violet-200 bg-white px-3.5 py-2 text-xs font-semibold text-violet-700 shadow-sm hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
    >
      {alreadyDisabled ? "Rebuild in progress…" : "Rebuild matches for this profile"}
    </button>
  );
}

export function RebuildBanner({ profileId }: { profileId: string | null }) {
  const status = useMatchRebuildStatus(profileId);
  const queryClient = useQueryClient();
  const data = status.data;
  const runId = data?.id ?? null;
  const staleCount = data?.stale_count ?? 0;
  const active = isRebuildActive(data?.status);
  const needsAttention = runId !== null && data !== undefined && data.status === "failed";

  useEffect(() => {
    if (data?.status === "succeeded" && profileId !== null) {
      void queryClient.invalidateQueries({ queryKey: ["matches", profileId] });
    }
    // Invalidate the ranked list once, when a rebuild lands.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, data?.status]);

  // Hidden entirely for a clean profile with nothing to act on: the affordance
  // only appears when there is a discrepancy, an active run, or a failed one.
  if (profileId === null || (staleCount === 0 && !active && !needsAttention)) return null;

  return (
    <section
      aria-label="Match rebuild"
      className="flex flex-col gap-2 rounded-2xl border border-amber-200 bg-amber-50/60 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        {staleCount > 0 && (
          <p className="text-xs font-semibold text-amber-900">
            {staleCount} stored match{staleCount === 1 ? "" : "es"} not found by this profile&apos;s
            searches — rebuilding refreshes scores and removes them.
          </p>
        )}
        {active && data !== undefined && (
          <p className="text-xs font-semibold text-gray-900" aria-live="polite">
            {STATUS_LABELS[data.status] ?? data.status}
          </p>
        )}
        {needsAttention && (
          <p role="alert" className="text-xs font-semibold text-red-700">
            Rebuild failed — {data?.warning ?? "unexpected error; try again."}
          </p>
        )}
        <RebuildTrigger profileId={profileId} disabled={active} />
      </div>
      {active && (
        <p className="text-xs text-gray-600" aria-live="polite">
          Rebuilding in the background — you can close this dialog; the run keeps going.
        </p>
      )}
      {runId !== null && !active && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant={data?.status === "succeeded" ? "success" : "warn"}>{data?.status}</Badge>
          <span className="text-gray-600">
            corpus: {data?.corpus_count ?? 0} posting(s) · scored: {data?.scored_count ?? 0}
          </span>
          {data?.warning && (
            <span className="text-amber-700" role="alert">
              {data.warning}
            </span>
          )}
        </div>
      )}
    </section>
  );
}
