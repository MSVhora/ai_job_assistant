"use client";

import {
  keepPreviousData,
  skipToken,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  bulkApprove,
  confirmMetric,
  editAchievement,
  getAchievement,
  getBulkEligible,
  linkEvidence,
  listAchievementsPage,
  listMergeProposals,
  listRevisions,
  mergeAchievements,
  runAchievementAction,
  splitAchievement,
  unlinkEvidence,
  type AchievementAction,
  type AchievementListParams,
  type AchievementUpdate,
  type ConfirmMetricRequest,
  type EvidenceLinkCreate,
  type MergeRequest,
  type SplitRequest,
} from "@/lib/api";

export function useAchievements(params: AchievementListParams) {
  return useQuery({
    queryKey: ["achievements", params],
    queryFn: () => listAchievementsPage(params),
    placeholderData: keepPreviousData,
  });
}

export function useAchievement(achievementId: string | null) {
  return useQuery({
    queryKey: ["achievement", achievementId],
    queryFn: achievementId !== null ? () => getAchievement(achievementId) : skipToken,
  });
}

export function useRevisions(achievementId: string | null) {
  return useQuery({
    queryKey: ["achievement-revisions", achievementId],
    queryFn: achievementId !== null ? () => listRevisions(achievementId) : skipToken,
  });
}

export function useMergeProposals() {
  return useQuery({ queryKey: ["merge-proposals"], queryFn: listMergeProposals });
}

export function useBulkEligible(enabled: boolean) {
  return useQuery({
    queryKey: ["bulk-eligible"],
    queryFn: getBulkEligible,
    enabled,
    gcTime: 0,
  });
}

function useRefreshAchievements() {
  const queryClient = useQueryClient();
  return () => {
    for (const key of [
      "achievements",
      "achievement",
      "achievement-revisions",
      "merge-proposals",
      "bulk-eligible",
    ]) {
      void queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
}

export function useAchievementAction() {
  const refresh = useRefreshAchievements();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: AchievementAction }) =>
      runAchievementAction(id, action),
    onSuccess: refresh,
  });
}

export function useEditAchievement() {
  const refresh = useRefreshAchievements();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AchievementUpdate }) =>
      editAchievement(id, payload),
    onSuccess: refresh,
  });
}

export function useConfirmMetric() {
  const refresh = useRefreshAchievements();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ConfirmMetricRequest }) =>
      confirmMetric(id, payload),
    onSuccess: refresh,
  });
}

export function useLinkEvidence() {
  const refresh = useRefreshAchievements();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: EvidenceLinkCreate }) =>
      linkEvidence(id, payload),
    onSuccess: refresh,
  });
}

export function useUnlinkEvidence() {
  const refresh = useRefreshAchievements();
  return useMutation({
    mutationFn: ({ id, itemId }: { id: string; itemId: string }) => unlinkEvidence(id, itemId),
    onSuccess: refresh,
  });
}

export function useSplitAchievement() {
  const refresh = useRefreshAchievements();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SplitRequest }) =>
      splitAchievement(id, payload),
    onSuccess: refresh,
  });
}

export function useMergeAchievements() {
  const refresh = useRefreshAchievements();
  return useMutation({
    mutationFn: (payload: MergeRequest) => mergeAchievements(payload),
    onSuccess: refresh,
  });
}

export function useBulkApprove() {
  const refresh = useRefreshAchievements();
  return useMutation({ mutationFn: (ids: string[]) => bulkApprove(ids), onSuccess: refresh });
}
