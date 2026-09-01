"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { gapFillTurn, type GapFillMessage } from "@/lib/api";

export function useGapFillTurn(profileId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messages: GapFillMessage[]) => gapFillTurn(profileId, messages),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile", profileId] });
      void queryClient.invalidateQueries({ queryKey: ["profiles"] });
    },
  });
}
