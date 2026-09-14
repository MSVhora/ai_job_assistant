"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getMatchRebuildStatus, startMatchRebuild } from "@/lib/api";

const ACTIVE_STATUSES = new Set(["pending", "running"]);
const POLL_INTERVAL_MS = 1500;

export function isRebuildActive(status: string | undefined): boolean {
  return status !== undefined && ACTIVE_STATUSES.has(status);
}

export function useMatchRebuildStatus(profileId: string | null) {
  return useQuery({
    queryKey: ["match-rebuild", profileId],
    queryFn: () => getMatchRebuildStatus(profileId as string),
    enabled: profileId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status !== undefined && ACTIVE_STATUSES.has(status) ? POLL_INTERVAL_MS : false;
    },
  });
}

export function useStartMatchRebuild() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profileId: string) => startMatchRebuild(profileId),
    onSuccess: (_data, profileId) => {
      void queryClient.invalidateQueries({ queryKey: ["match-rebuild", profileId] });
    },
  });
}
