"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getJobSearchStatus,
  getSearchPostings,
  regenerateSearchQueries,
  startJobSearch,
  type JobSearchRequest,
} from "@/lib/api";

const ACTIVE_STATUSES = new Set(["pending", "running"]);
const POLL_INTERVAL_MS = 1500;
const TERMINAL_STATUSES = new Set(["succeeded", "partial", "failed"]);

export function useJobSearchStatus(searchId: string | null) {
  return useQuery({
    queryKey: ["job-search", searchId],
    queryFn: () => getJobSearchStatus(searchId as string),
    enabled: searchId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status !== undefined && ACTIVE_STATUSES.has(status) ? POLL_INTERVAL_MS : false;
    },
  });
}

export function useSearchPostings(searchId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["job-search-postings", searchId],
    queryFn: () => getSearchPostings(searchId as string),
    enabled: searchId !== null && enabled,
  });
}

export function isRunFinished(status: string | undefined): boolean {
  return status !== undefined && TERMINAL_STATUSES.has(status);
}

export function useStartJobSearch() {
  return useMutation({ mutationFn: (payload: JobSearchRequest) => startJobSearch(payload) });
}

export function useRegenerateQueries() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ profileId, sources }: { profileId: string; sources?: string[] }) =>
      regenerateSearchQueries(profileId, sources),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
