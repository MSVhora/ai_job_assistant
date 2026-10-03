"use client";

import { skipToken, useQuery } from "@tanstack/react-query";

import { getResumeDraft, type DraftProfileResponse } from "@/lib/api";

export function useResumeDraft(resumeId: string | null) {
  return useQuery<DraftProfileResponse>({
    queryKey: ["resume-draft", resumeId],
    queryFn: resumeId !== null ? () => getResumeDraft(resumeId) : skipToken,
  });
}
