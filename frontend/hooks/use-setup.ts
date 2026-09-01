"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { enableSource, getSetupCheck, listSources } from "@/lib/api";

export function useSetupCheck() {
  return useQuery({ queryKey: ["setup-check"], queryFn: getSetupCheck });
}

export function useSources() {
  return useQuery({ queryKey: ["sources"], queryFn: listSources });
}

export function useEnableSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, acknowledged }: { name: string; acknowledged: boolean }) =>
      enableSource(name, acknowledged),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });
}
