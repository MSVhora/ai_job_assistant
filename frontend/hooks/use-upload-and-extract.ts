"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { extractResume, uploadResume, type DraftProfileResponse } from "@/lib/api";

export function useExtractResume() {
  const queryClient = useQueryClient();
  return useMutation<DraftProfileResponse, Error, string>({
    mutationFn: (resumeId) => extractResume(resumeId),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
  });
}

export function useUploadAndExtract() {
  const queryClient = useQueryClient();
  return useMutation<DraftProfileResponse, Error, File>({
    mutationFn: async (file) => {
      const uploaded = await uploadResume(file);
      return await extractResume(uploaded.resume_id);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
  });
}
