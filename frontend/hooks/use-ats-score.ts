"use client";

import { useMutation } from "@tanstack/react-query";

import { scoreAts, type AtsScoreResponse, type AtsScoreRequest } from "@/lib/api";

export function useAtsScore() {
  return useMutation<AtsScoreResponse, Error, AtsScoreRequest>({
    mutationFn: (payload) => scoreAts(payload),
  });
}
