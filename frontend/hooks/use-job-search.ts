"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getJobSearchStatus,
  getSearchPostings,
  listProfileSearches,
  regenerateSearchQueries,
  startJobSearch,
  tuneSearchQueries,
  type JobSearchRequest,
} from "@/lib/api";
const ACTIVE_STATUSES = new Set(["pending", "running"]);
const POLL_INTERVAL_MS = 1500;
const TERMINAL_STATUSES = new Set(["succeeded", "partial", "failed"]);

export function useJobSearchStatus(searchId: string | null, profileId: string | null) {
  return useQuery({
    queryKey: ["job-search", searchId, profileId],
    queryFn: () => getJobSearchStatus(searchId as string, profileId as string),
    enabled: searchId !== null && profileId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status !== undefined && ACTIVE_STATUSES.has(status) ? POLL_INTERVAL_MS : false;
    },
  });
}

export function useSearchPostings(
  searchId: string | null,
  profileId: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["job-search-postings", searchId, profileId],
    queryFn: () => getSearchPostings(searchId as string, profileId as string),
    enabled: searchId !== null && profileId !== null && enabled,
  });
}

export function isRunFinished(status: string | undefined): boolean {
  return status !== undefined && TERMINAL_STATUSES.has(status);
}

export function isRunActive(status: string): boolean {
  return ACTIVE_STATUSES.has(status);
}

export function useProfileSearches(profileId: string | null) {
  return useQuery({
    queryKey: ["profile-searches", profileId],
    queryFn: () => listProfileSearches(profileId as string),
    enabled: profileId !== null,
  });
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

export function useTuneQueries() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profileId: string) => tuneSearchQueries(profileId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["matches"] });
    },
  });
}
