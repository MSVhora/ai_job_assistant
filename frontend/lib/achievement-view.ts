import type { Achievement } from "@/lib/api";

export type MetricVerification = "evidence" | "user" | "needs_confirmation";

export interface MetricView {
  index: number;
  text: string;
  sourceQuote: string | null;
  verified: MetricVerification;
}

const FLAG_LABELS: Record<string, string> = {
  contains_redaction_placeholder: "Contains a redaction placeholder",
  metric_needs_confirmation: "A metric needs confirmation",
  result_removed_unsupported: "Result removed: no supporting quote",
  merged: "Merged from several achievements",
  split: "Split from another achievement",
};

export const IMPACT_LABELS: Record<string, string> = {
  performance: "Performance",
  reliability: "Reliability",
  revenue: "Revenue",
  cost: "Cost",
  quality: "Quality",
  velocity: "Velocity",
  scale: "Scale",
  security: "Security",
  ux: "UX",
  leadership: "Leadership",
  other: "Other",
};

export function metricViews(achievement: Achievement): MetricView[] {
  return achievement.metrics.map((metric, index) => {
    const verified =
      metric.verified === "evidence" || metric.verified === "user"
        ? metric.verified
        : "needs_confirmation";
    return {
      index,
      text: typeof metric.text === "string" ? metric.text : "",
      sourceQuote:
        typeof metric.source_quote === "string" && metric.source_quote !== ""
          ? metric.source_quote
          : null,
      verified,
    };
  });
}

export function pendingMetricCount(achievement: Achievement): number {
  return metricViews(achievement).filter((metric) => metric.verified === "needs_confirmation")
    .length;
}

export function approvalBlockers(achievement: Achievement): string[] {
  const blockers: string[] = [];
  if ((achievement.evidence ?? []).length === 0)
    blockers.push("Link at least one piece of evidence");
  const pending = pendingMetricCount(achievement);
  if (pending > 0) blockers.push(`Confirm ${pending} metric${pending === 1 ? "" : "s"}`);
  return blockers;
}

export function flagLabel(flag: string): string {
  return FLAG_LABELS[flag] ?? flag;
}

export function isStale(achievement: Achievement): boolean {
  return achievement.evidence_stale_at !== null;
}

export function parseSkills(input: string): string[] {
  return input
    .split(",")
    .map((skill) => skill.trim())
    .filter((skill, index, all) => skill !== "" && all.indexOf(skill) === index);
}

export function formatRevisionDiff(diff: Record<string, unknown>): string[] {
  return Object.entries(diff).map(([field, change]) => {
    if (Array.isArray(change) && change.length === 2) {
      return `${field}: ${JSON.stringify(change[0])} → ${JSON.stringify(change[1])}`;
    }
    return `${field}: ${JSON.stringify(change)}`;
  });
}

const GITHUB_REPO = /^[\w.-]+\/[\w.-]+$/;

/** Link to the source repository when the project key is an `owner/repo`, else null. */
export function repositoryUrl(projectKey: string | null | undefined): string | null {
  return projectKey !== null && projectKey !== undefined && GITHUB_REPO.test(projectKey)
    ? `https://github.com/${projectKey}`
    : null;
}

export type EmployerSource = "user" | "scope" | "suggested";

/** Who set the achievement's employer: you, its repository's mapping, or the app's suggestion. */
export function employerSource(
  ref: Record<string, unknown> | null | undefined,
): EmployerSource | null {
  const source = ref?.source;
  return source === "user" || source === "scope" || source === "suggested" ? source : null;
}

export const EMPLOYER_SOURCE_NOTES: Record<EmployerSource, string> = {
  user: "set by you",
  scope: "from the repository",
  suggested: "suggested",
};
