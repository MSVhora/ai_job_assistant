"use client";

import { useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { recordMatchSignal, type MatchResponse, type MatchSignalKind } from "@/lib/api";

/**
 * Engagement signals (#39): save/dismiss writes fire the POST signal endpoint
 * and reconcile the matches cache with the server's response; the open signal
 * is fire-and-forget from the detail panel (the server stays idempotent).
 */
export function useMatchSignal(profileId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, kind }: { matchId: string; kind: MatchSignalKind }) =>
      recordMatchSignal(matchId, kind),
    onSuccess: (updated: MatchResponse) => {
      queryClient.setQueriesData<{ items: MatchResponse[]; total: number }>(
        { queryKey: ["matches", profileId] },
        (page) =>
          page === undefined
            ? page
            : {
                ...page,
                items: page.items.map((match) =>
                  match.id === updated.id ? updated : match,
                ),
              },
      );
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["matches", profileId] });
    },
  });
}

export function useOpenMatchSignal() {
  const queryClient = useQueryClient();
  return useCallback(
    async (matchId: string) => {
      try {
        await recordMatchSignal(matchId, "open");
        void queryClient.invalidateQueries({ queryKey: ["matches"] });
      } catch (cause) {
        if (cause instanceof Error) {
          console.warn("opening signal failed:", cause.message);
        }
      }
    },
    [queryClient],
  );
}
