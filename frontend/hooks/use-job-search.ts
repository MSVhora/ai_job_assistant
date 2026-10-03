"use client";

import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  estimateRegenerateQueries,
  estimateTuneQueries,
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
    queryFn:
      searchId !== null && profileId !== null
        ? () => getJobSearchStatus(searchId, profileId)
        : skipToken,
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
    queryFn:
      searchId !== null && profileId !== null && enabled
        ? () => getSearchPostings(searchId, profileId)
        : skipToken,
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
    queryFn: profileId !== null ? () => listProfileSearches(profileId) : skipToken,
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

export function useRegenerateEstimate(profileId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["regenerate-estimate", profileId],
    queryFn: enabled && profileId !== null ? () => estimateRegenerateQueries(profileId) : skipToken,
    gcTime: 0,
    retry: false,
  });
}

export function useTuneEstimate(profileId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["tune-estimate", profileId],
    queryFn: enabled && profileId !== null ? () => estimateTuneQueries(profileId) : skipToken,
    gcTime: 0,
    retry: false,
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
