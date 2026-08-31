"use client";

import { useQuery } from "@tanstack/react-query";

import { ApiError, getProfile, type ProfileResponse } from "@/lib/api";

export function useProfile() {
  return useQuery<ProfileResponse | null>({
    queryKey: ["profile"],
    queryFn: async () => {
      try {
        return await getProfile();
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
  });
}
