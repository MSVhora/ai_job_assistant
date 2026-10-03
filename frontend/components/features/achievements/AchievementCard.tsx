"use client";

import { Button } from "@/components/ui/button";
import type { Achievement } from "@/lib/api";
import { approvalBlockers } from "@/lib/achievement-view";

import { AchievementBadges } from "./AchievementBadges";

export function AchievementCard({
  achievement,
  selected,
  selectable,
  busy,
  onSelect,
  onOpen,
  onApprove,
  onReject,
}: {
  achievement: Achievement;
  selected: boolean;
  selectable: boolean;
  busy: boolean;
  onSelect: (selected: boolean) => void;
  onOpen: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const blockers = approvalBlockers(achievement);
  const isDraft = achievement.status === "draft";
  const evidenceCount = (achievement.evidence ?? []).length;
  return (
    <li className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        {selectable && (
          <input
            type="checkbox"
            aria-label={`Select ${achievement.title} for merging`}
            checked={selected}
            onChange={(event) => {
              onSelect(event.target.checked);
            }}
            className="mt-1 h-4 w-4 rounded border-gray-300 text-violet-600"
          />
        )}
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={onOpen}
            className="text-left text-base font-bold text-gray-900 hover:text-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            {achievement.title}
          </button>
          <p className="mt-1 line-clamp-2 text-sm text-gray-600">
            {achievement.result ?? achievement.action ?? ""}
          </p>
          <div className="mt-2">
            <AchievementBadges achievement={achievement} />
          </div>
          {achievement.skills.length > 0 && (
            <p className="mt-2 text-xs text-gray-500">{achievement.skills.join(" · ")}</p>
          )}
          <p className="mt-1 text-xs text-gray-500">
            {evidenceCount} evidence item{evidenceCount === 1 ? "" : "s"}
          </p>
        </div>
        {isDraft && (
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <Button disabled={busy || blockers.length > 0} onClick={onApprove}>
              Approve
            </Button>
            <Button variant="secondary" disabled={busy} onClick={onReject}>
              Reject
            </Button>
            {blockers.length > 0 && (
              <p className="max-w-40 text-right text-xs text-amber-800">{blockers.join("; ")}</p>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
