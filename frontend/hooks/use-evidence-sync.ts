"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getEvidenceStatus,
  listEmployers,
  listGithubScopes,
  listSyncs,
  startGithubSync,
  updateGithubScopes,
  type ScopeUpdateItem,
  type SyncMode,
} from "@/lib/api";
import { isActiveStatus } from "@/lib/evidence-progress";

const POLL_INTERVAL_MS = 2000;

export function useEvidenceStatus() {
  return useQuery({ queryKey: ["evidence-status"], queryFn: getEvidenceStatus });
}

export function useGithubScopes(enabled: boolean) {
  return useQuery({
    queryKey: ["evidence-scopes"],
    queryFn: listGithubScopes,
    enabled,
    staleTime: 60_000,
  });
}

export function useEmployers() {
  return useQuery({ queryKey: ["evidence-employers"], queryFn: listEmployers });
}

export function useUpdateScopes() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ scopes, acknowledged }: { scopes: ScopeUpdateItem[]; acknowledged: boolean }) =>
      updateGithubScopes(scopes, acknowledged),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["evidence-scopes"] });
      void queryClient.invalidateQueries({ queryKey: ["evidence-status"] });
      void queryClient.invalidateQueries({ queryKey: ["achievements"] });
    },
  });
}

export function useLatestSync() {
  return useQuery({
    queryKey: ["evidence-sync-latest"],
    queryFn: async () => (await listSyncs(1))[0] ?? null,
    refetchInterval: (query) =>
      isActiveStatus(query.state.data?.status) ? POLL_INTERVAL_MS : false,
  });
}

export function useStartSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mode: SyncMode) => startGithubSync(mode),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["evidence-sync-latest"] });
      void queryClient.invalidateQueries({ queryKey: ["evidence-status"] });
    },
  });
}
