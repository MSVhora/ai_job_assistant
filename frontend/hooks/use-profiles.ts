"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProfile,
  deleteProfile,
  getProfile,
  listProfiles,
  updatePreferences,
  updateProfile,
  type ProfileCreate,
  type ProfileUpdate,
  type StoredPreferences,
} from "@/lib/api";

export function useProfiles() {
  return useQuery({ queryKey: ["profiles"], queryFn: listProfiles });
}

export function useProfile(profileId: string | null) {
  return useQuery({
    queryKey: ["profile", profileId],
    queryFn: () => getProfile(profileId as string),
    enabled: profileId !== null,
  });
}

export function useCreateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProfileCreate) => createProfile(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profiles"] });
      void queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ profileId, payload }: { profileId: string; payload: ProfileUpdate }) =>
      updateProfile(profileId, payload),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["profiles"] });
      void queryClient.invalidateQueries({ queryKey: ["profile", data.profile_id] });
      void queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
  });
}

export function useDeleteProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profileId: string) => deleteProfile(profileId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profiles"] });
      void queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ profileId, payload }: { profileId: string; payload: StoredPreferences }) =>
      updatePreferences(profileId, payload),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["profile", variables.profileId] });
    },
  });
}
