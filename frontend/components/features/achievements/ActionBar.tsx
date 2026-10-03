"use client";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAchievementAction } from "@/hooks/use-achievements";
import type { Achievement, AchievementAction } from "@/lib/api";
import { approvalBlockers, isStale } from "@/lib/achievement-view";

const DONE: Record<AchievementAction, string> = {
  approve: "Approved",
  reject: "Rejected",
  archive: "Archived",
  unapprove: "Moved back to drafts",
  restore: "Restored to drafts",
  acknowledge: "Marked as re-reviewed",
};

export function ActionBar({
  achievement,
  onClose,
}: {
  achievement: Achievement;
  onClose: () => void;
}) {
  const action = useAchievementAction();
  const blockers = approvalBlockers(achievement);

  const run = (name: AchievementAction, closeAfter = true) => {
    action.mutate(
      { id: achievement.id, action: name },
      {
        onSuccess: () => {
          toast.success(DONE[name]);
          if (closeAfter) onClose();
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {achievement.status === "draft" && (
          <>
            <Button
              disabled={action.isPending || blockers.length > 0}
              onClick={() => {
                run("approve");
              }}
            >
              Approve
            </Button>
            <Button
              variant="secondary"
              disabled={action.isPending}
              onClick={() => {
                run("reject");
              }}
            >
              Reject
            </Button>
          </>
        )}
        {achievement.status === "approved" && (
          <>
            {isStale(achievement) && (
              <Button
                disabled={action.isPending}
                onClick={() => {
                  run("acknowledge", false);
                }}
              >
                I re-reviewed the evidence
              </Button>
            )}
            <Button
              variant="secondary"
              disabled={action.isPending}
              onClick={() => {
                run("unapprove");
              }}
            >
              Unapprove
            </Button>
            <Button
              variant="secondary"
              disabled={action.isPending}
              onClick={() => {
                run("archive");
              }}
            >
              Archive
            </Button>
          </>
        )}
        {achievement.status === "rejected" && (
          <Button
            variant="secondary"
            disabled={action.isPending}
            onClick={() => {
              run("restore");
            }}
          >
            Restore to drafts
          </Button>
        )}
      </div>
      {achievement.status === "draft" && blockers.length > 0 && (
        <p role="status" className="text-xs text-amber-800">
          Can&apos;t approve yet: {blockers.join("; ")}.
        </p>
      )}
    </div>
  );
}
