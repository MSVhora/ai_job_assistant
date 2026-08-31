"use client";

import { useQuery } from "@tanstack/react-query";

import { getResumeDraft, type DraftProfileResponse } from "@/lib/api";

export function useResumeDraft(resumeId: string | null) {
  return useQuery<DraftProfileResponse>({
    queryKey: ["resume-draft", resumeId],
    queryFn: () => getResumeDraft(resumeId as string),
    enabled: resumeId !== null,
  });
}
