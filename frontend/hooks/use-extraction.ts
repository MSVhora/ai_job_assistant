"use client";

import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { estimateExtraction, getExtractionRun, startExtraction } from "@/lib/api";
import { isActiveStatus } from "@/lib/evidence-progress";

const POLL_INTERVAL_MS = 2000;

export function useEstimateExtraction() {
  return useMutation({ mutationFn: estimateExtraction });
}

export function useStartExtraction() {
  return useMutation({ mutationFn: (estimateId: string) => startExtraction(estimateId) });
}

export function useExtractionRun(runId: string | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["extraction-run", runId],
    queryFn:
      runId !== null
        ? async () => {
            const run = await getExtractionRun(runId);
            if (!isActiveStatus(run.status)) {
              void queryClient.invalidateQueries({ queryKey: ["achievements"] });
              void queryClient.invalidateQueries({ queryKey: ["evidence-chunks"] });
            }
            return run;
          }
        : skipToken,
    refetchInterval: (query) =>
      isActiveStatus(query.state.data?.status) ? POLL_INTERVAL_MS : false,
  });
}
