"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { getJobSearchStatus, startJobSearch, type JobSearchRequest } from "@/lib/api";

const ACTIVE_STATUSES = new Set(["pending", "running"]);
const POLL_INTERVAL_MS = 1500;

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

export function useStartJobSearch() {
  return useMutation({ mutationFn: (payload: JobSearchRequest) => startJobSearch(payload) });
}
