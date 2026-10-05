import type { AchievementListParams } from "@/lib/api";
import { employerParams } from "@/lib/draft-groups";

export type ReviewTab = "draft" | "approved" | "rejected" | "attention";

export const PAGE_SIZE = 20;

export const TABS: { id: ReviewTab; label: string }[] = [
  { id: "draft", label: "Draft" },
  { id: "approved", label: "Approved" },
  { id: "rejected", label: "Rejected" },
  { id: "attention", label: "Needs attention" },
];

export const TAB_HINTS: Record<ReviewTab, string> = {
  draft: "Extracted achievements waiting for your decision. Nothing here is used yet.",
  approved: "Your knowledge base: only these are used for resumes and the interview agent.",
  rejected: "Set aside. You can restore any of them.",
  attention: "Approved achievements whose evidence changed after a refresh: look again.",
};

export function paramsForTab(
  tab: ReviewTab,
  privateOnly: boolean,
  offset: number,
  repository = "",
  employer = "",
): AchievementListParams {
  const base: AchievementListParams = {
    status: tab === "attention" ? "approved" : tab,
    limit: PAGE_SIZE,
    offset,
    ...(tab === "attention" ? { stale: true } : {}),
    ...(privateOnly ? { private: true } : {}),
    ...(repository === "" ? {} : { project_key: repository }),
    ...employerParams(employer),
  };
  return base;
}
