"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { listMatches, type MatchListParams } from "@/lib/api";

export type MatchFilterValues = Pick<
  MatchListParams,
  "location" | "remote_type" | "job_type" | "posted_within_days" | "sort"
>;

// Slider position equivalent to the server defaults (MATCH_WEIGHT_ROLE_FIT=0.4,
// MATCH_WEIGHT_COMPANY_FIT=0.2 → 0.4/0.6). Display default only; with no stored
// preference and no slider move, no priority is sent and the server decides.
export const DEFAULT_PRIORITY = 2 / 3;

export const DEFAULT_MATCH_FILTERS: MatchFilterValues = {
  location: undefined,
  remote_type: undefined,
  job_type: undefined,
  posted_within_days: undefined,
  sort: "final_score",
};

export function useMatches(
  profileId: string | null,
  params: Pick<MatchListParams, "limit" | "offset" | "priority"> & MatchFilterValues,
) {
  return useQuery({
    queryKey: ["matches", profileId, params],
    queryFn: () => listMatches({ profile_id: profileId as string, ...params }),
    enabled: profileId !== null,
    placeholderData: keepPreviousData,
  });
}
