import { Badge } from "@/components/ui/badge";
import type { Achievement } from "@/lib/api";
import { flagLabel, IMPACT_LABELS, isStale, pendingMetricCount } from "@/lib/achievement-view";
import { SourceBadges } from "./SourceBadges";

export function AchievementBadges({ achievement }: { achievement: Achievement }) {
  const pending = pendingMetricCount(achievement);
  return (
    <div className="flex flex-wrap gap-1.5">
      {achievement.derived_from_private && <Badge variant="warn">Private repo</Badge>}
      {isStale(achievement) && <Badge variant="danger">Evidence updated — re-review</Badge>}
      {pending > 0 && <Badge variant="warn">{pending} to confirm</Badge>}
      <Badge variant="ai">
        {IMPACT_LABELS[achievement.impact_type] ?? achievement.impact_type}
      </Badge>
      <Badge>Difficulty {achievement.difficulty}/5</Badge>
      <SourceBadges achievement={achievement} />
      {achievement.review_flags
        .filter((flag) => flag !== "metric_needs_confirmation")
        .map((flag) => (
          <Badge key={flag} variant="warn">
            {flagLabel(flag)}
          </Badge>
        ))}
    </div>
  );
}
