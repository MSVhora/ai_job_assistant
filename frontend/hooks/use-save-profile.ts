"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { patchProfile, type ProfileUpdateRequest } from "@/lib/api";

export function useSaveProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProfileUpdateRequest) => patchProfile(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
