"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  addProfileExperience,
  estimateEmployerMergeSuggestions,
  listEmployers,
  mergeEmployers,
  suggestEmployerMerges,
  unmergeEmployer,
  type EmployerMergeRequest,
  type EmployerOption,
  type ExperienceCreate,
} from "@/lib/api";

const EMPLOYERS_KEY = ["evidence-employers"];

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
