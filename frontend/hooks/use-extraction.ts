"use client";

import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  estimateExtraction,
  getExtractionRun,
  listExtractionRuns,
  startExtraction,
} from "@/lib/api";
import { isActiveStatus } from "@/lib/evidence-progress";

const POLL_INTERVAL_MS = 2000;

export function useEstimateExtraction() {
  return useMutation({ mutationFn: estimateExtraction });
}

export function useStartExtraction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (estimateId: string) => startExtraction(estimateId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["extraction-latest"] }),
  });
}

/** The newest extraction run, so a run that is still going is found again after a reload. */
export function useLatestExtraction() {
  return useQuery({
    queryKey: ["extraction-latest"],
    queryFn: async () => (await listExtractionRuns(1))[0] ?? null,
    refetchInterval: (query) =>
      isActiveStatus(query.state.data?.status) ? POLL_INTERVAL_MS : false,
  });
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
