"use client";

import { useMutation } from "@tanstack/react-query";

import { extractResume, uploadResume, type DraftProfileResponse } from "@/lib/api";

export function useUploadAndExtract() {
  return useMutation<DraftProfileResponse, Error, File>({
    mutationFn: async (file) => {
      const uploaded = await uploadResume(file);
      return await extractResume(uploaded.resume_id);
    },
  });
}
