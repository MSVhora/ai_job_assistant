"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addProfileExperience,
  estimateEmployerMergeSuggestions,
  listEmployers,
  listOwners,
  mergeEmployers,
  setOwnerEmployer,
  suggestEmployerMerges,
  unmergeEmployer,
  type EmployerMergeRequest,
  type EmployerOption,
  type OwnerSummary,
  type ExperienceCreate,
} from "@/lib/api";

const EMPLOYERS_KEY = ["evidence-employers"];
const OWNERS_KEY = ["evidence-owners"];

function useRefreshAfterEmployerChange() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: EMPLOYERS_KEY }),
      queryClient.invalidateQueries({ queryKey: ["evidence-scopes"] }),
      queryClient.invalidateQueries({ queryKey: ["achievements"] }),
    ]);
  };
}

/** Adds a role to a profile; the employer list is refetched before the caller continues. */
export function useAddEmployer() {
  const queryClient = useQueryClient();
  const refresh = useRefreshAfterEmployerChange();
  return useMutation({
    mutationFn: ({ profileId, payload }: { profileId: string; payload: ExperienceCreate }) =>
      addProfileExperience(profileId, payload),
    onSuccess: async (_profile, { profileId }) => {
      await Promise.all([
        queryClient.query({ queryKey: EMPLOYERS_KEY, queryFn: listEmployers, staleTime: 0 }),
        refresh(),
        queryClient.invalidateQueries({ queryKey: ["profile", profileId] }),
        queryClient.invalidateQueries({ queryKey: ["profiles"] }),
      ]);
    },
  });
}

export function useMergeEmployers() {
  const queryClient = useQueryClient();
  const refresh = useRefreshAfterEmployerChange();
  return useMutation({
    mutationFn: (payload: EmployerMergeRequest) => mergeEmployers(payload),
    onSuccess: async (options: EmployerOption[]) => {
      queryClient.setQueryData(EMPLOYERS_KEY, options);
      await refresh();
    },
  });
}

export function useUnmergeEmployer() {
  const queryClient = useQueryClient();
  const refresh = useRefreshAfterEmployerChange();
  return useMutation({
    mutationFn: (key: string) => unmergeEmployer(key),
    onSuccess: async (options: EmployerOption[]) => {
      queryClient.setQueryData(EMPLOYERS_KEY, options);
      await refresh();
    },
  });
}

export function useEstimateMergeSuggestions() {
  return useMutation({ mutationFn: estimateEmployerMergeSuggestions });
}

export function useSuggestMerges() {
  return useMutation({ mutationFn: suggestEmployerMerges });
}

export function useOwners(enabled: boolean) {
  return useQuery({ queryKey: OWNERS_KEY, queryFn: listOwners, enabled });
}

export function useSetOwnerEmployer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      owner,
      employerRef,
    }: {
      owner: string;
      employerRef: Record<string, unknown> | null;
    }) => setOwnerEmployer(owner, employerRef),
    onSuccess: async (owners: OwnerSummary[]) => {
      queryClient.setQueryData(OWNERS_KEY, owners);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["evidence-scopes"] }),
        queryClient.invalidateQueries({ queryKey: ["achievements"] }),
      ]);
    },
  });
}
