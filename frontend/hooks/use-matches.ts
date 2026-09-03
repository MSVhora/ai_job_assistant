"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { listMatches, type MatchListParams } from "@/lib/api";

export type MatchFilterValues = Pick<
  MatchListParams,
  "location" | "remote_type" | "job_type" | "posted_within_days" | "sort"
>;

export const DEFAULT_MATCH_FILTERS: MatchFilterValues = {
  location: undefined,
  remote_type: undefined,
  job_type: undefined,
  posted_within_days: undefined,
  sort: "final_score",
};

export function useMatches(
  profileId: string | null,
  params: Pick<MatchListParams, "limit" | "offset"> & MatchFilterValues,
) {
  return useQuery({
    queryKey: ["matches", profileId, params],
    queryFn: () => listMatches({ profile_id: profileId as string, ...params }),
    enabled: profileId !== null,
    placeholderData: keepPreviousData,
  });
}
