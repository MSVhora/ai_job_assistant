import { Badge } from "@/components/ui/badge";
import type { Achievement } from "@/lib/api";
import { EMPLOYER_SOURCE_NOTES, employerSource, repositoryUrl } from "@/lib/achievement-view";
import { employerLabel } from "@/lib/evidence-progress";

const LINK =
  "inline-flex items-center gap-1 rounded-full border border-gray-300 bg-gray-50 px-2.5 py-0.5 text-xs font-medium text-gray-700 hover:bg-violet-50 hover:text-violet-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600";

/** Where an achievement came from (its repository) and who it is attributed to (its employer). */
export function SourceBadges({ achievement }: { achievement: Achievement }) {
  const url = repositoryUrl(achievement.project_key);
  const employer = employerLabel(achievement.employer_ref);
  const source = employerSource(achievement.employer_ref);
  return (
    <>
      {achievement.project_key !== null &&
        (url !== null ? (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className={LINK}
            aria-label={`Repository ${achievement.project_key}`}
          >
            {achievement.project_key}
          </a>
        ) : (
          <Badge>Source: {achievement.project_key}</Badge>
        ))}
      {employer !== null ? (
        <Badge variant={source === "suggested" ? "warn" : "neutral"}>
          Employer: {employer}
          {source !== null && ` · ${EMPLOYER_SOURCE_NOTES[source]}`}
        </Badge>
      ) : (
        <Badge variant="warn">Employer not set</Badge>
      )}
    </>
  );
}
