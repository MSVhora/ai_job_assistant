"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getEvidenceStatus,
  getTokenCheck,
  listEmployers,
  listGithubScopes,
  refreshGithubScopes,
  listSyncs,
  startGithubSync,
  updateGithubScopes,
  type ScopeUpdateItem,
  type SyncMode,
} from "@/lib/api";
import { isActiveStatus } from "@/lib/evidence-progress";
import { SCOPE_UPDATE_BATCH, chunk } from "@/lib/scope-draft";

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

export function useTokenCheck(enabled: boolean) {
  return useQuery({
    queryKey: ["evidence-token"],
    queryFn: getTokenCheck,
    enabled,
    staleTime: 60_000,
  });
}

export function useRefreshScopes() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: refreshGithubScopes,
    onSuccess: (scopes) => {
      queryClient.setQueryData(["evidence-scopes"], scopes);
      void queryClient.invalidateQueries({ queryKey: ["evidence-status"] });
      void queryClient.invalidateQueries({ queryKey: ["evidence-token"] });
    },
  });
}

export function useEmployers() {
  return useQuery({ queryKey: ["evidence-employers"], queryFn: listEmployers });
}

export function useUpdateScopes() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      scopes,
      acknowledged,
    }: {
      scopes: ScopeUpdateItem[];
      acknowledged: boolean;
    }) => {
      for (const batch of chunk(scopes, SCOPE_UPDATE_BATCH)) {
        await updateGithubScopes(batch, acknowledged);
      }
    },
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
