"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { isRebuildActive, useMatchRebuildStatus, useStartMatchRebuild } from "@/hooks/use-match-rebuild";

const STATUS_LABELS: Record<string, string> = {
  pending: "Rebuild queued…",
  running: "Re-scoring matches…",
  succeeded: "Matches rebuilt",
  failed: "Rebuild failed",
};

function RebuildTrigger({ profileId }: { profileId: string }) {
  const start = useStartMatchRebuild();
  const status = useMatchRebuildStatus(profileId);
  const disabled = start.isPending || isRebuildActive(status.data?.status);
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => start.mutate(profileId)}
      className="rounded-xl border border-violet-200 bg-white px-3.5 py-2 text-xs font-semibold text-violet-700 shadow-sm hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
    >
      {disabled ? "Rebuild in progress…" : "Rebuild matches for this profile"}
    </button>
  );
}

export function RebuildBanner({ profileId }: { profileId: string }) {
  const status = useMatchRebuildStatus(profileId);
  const queryClient = useQueryClient();
  const data = status.data;

  useEffect(() => {
    if (data?.status === "succeeded") {
      void queryClient.invalidateQueries({ queryKey: ["matches", profileId] });
    }
    // Invalidate the ranked list once, when a rebuild lands.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.id, data?.status]);

  return (
    <section
      aria-label="Match rebuild"
      className="flex flex-col gap-2 rounded-3xl border border-violet-100 bg-white/80 p-4 shadow-sm"
    >
      <RebuildTrigger profileId={profileId} />
      {status.isPending && !data?.id && (
        <p className="text-xs text-gray-500">No rebuild run yet for this profile.</p>
      )}
      {status.isError && (
        <p role="alert" className="text-xs text-red-700">
          Could not load the rebuild status.
        </p>
      )}
      {data !== undefined && (
        <div aria-live="polite" className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold text-gray-900">{STATUS_LABELS[data.status] ?? data.status}</span>
          <Badge variant={data.status === "succeeded" ? "success" : data.status === "failed" ? "danger" : "warn"}>
            {data.status}
          </Badge>
          <span className="text-gray-600">
            corpus: {data.corpus_count} posting(s) · scored: {data.scored_count}
          </span>
          {data.warning && (
            <span className="text-amber-700" role="alert">
              {data.warning}
            </span>
          )}
        </div>
      )}
      {isRebuildActive(data?.status) && (
        <p className="text-xs text-gray-500">
          Scoring runs in the background — you can leave this page; the run keeps going.
        </p>
      )}
    </section>
  );
}
