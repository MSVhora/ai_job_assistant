"use client";

import { useAchievementAction, useAchievements } from "@/hooks/use-achievements";
import { Button } from "@/components/ui/button";
import type { Achievement } from "@/lib/api";

import { AchievementCard } from "./AchievementCard";
import { PAGE_SIZE, paramsForTab, type ReviewTab } from "./review-tabs";

export function AchievementList({
  tab,
  privateOnly,
  repository,
  employer,
  offset,
  selected,
  onSelect,
  onOpen,
  onPage,
}: {
  tab: ReviewTab;
  privateOnly: boolean;
  repository: string;
  employer: string;
  offset: number;
  selected: ReadonlyMap<string, string>;
  onSelect: (achievement: Achievement, selected: boolean) => void;
  onOpen: (id: string) => void;
  onPage: (offset: number) => void;
}) {
  const list = useAchievements(paramsForTab(tab, privateOnly, offset, repository, employer));
  const action = useAchievementAction();

  if (list.isPending) {
    return <div className="h-40 animate-pulse rounded-2xl bg-white/70" aria-busy="true" />;
  }
  if (list.isError) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
      >
        Could not load achievements.
        <button
          type="button"
          className="ml-3 rounded-full border border-red-300 px-3 py-1 text-xs font-semibold"
          onClick={() => void list.refetch()}
        >
          Retry
        </button>
      </div>
    );
  }
  const { items, total } = list.data;
  if (items.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-gray-300 bg-white/70 p-6 text-center text-sm text-gray-600">
        Nothing here yet.
        {tab === "draft" && " Run an extraction on the Evidence page to create drafts."}
      </p>
    );
  }
  return (
    <>
      <ul className="flex flex-col gap-3" aria-label="Achievements">
        {items.map((achievement) => (
          <AchievementCard
            key={achievement.id}
            achievement={achievement}
            selected={selected.has(achievement.id)}
            selectable={tab === "draft" || tab === "approved"}
            busy={action.isPending}
            onSelect={(value) => {
              onSelect(achievement, value);
            }}
            onOpen={() => {
              onOpen(achievement.id);
            }}
            onApprove={() => {
              action.mutate({ id: achievement.id, action: "approve" });
            }}
            onReject={() => {
              action.mutate({ id: achievement.id, action: "reject" });
            }}
          />
        ))}
      </ul>
      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
          <Button
            variant="secondary"
            disabled={offset === 0}
            onClick={() => {
              onPage(Math.max(0, offset - PAGE_SIZE));
            }}
          >
            Previous
          </Button>
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <Button
            variant="secondary"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => {
              onPage(offset + PAGE_SIZE);
            }}
          >
            Next
          </Button>
        </div>
      )}
    </>
  );
}
