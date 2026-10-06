"use client";

import { Drawer } from "@/components/ui/drawer";
import { useAchievement } from "@/hooks/use-achievements";
import { KIND_LABELS } from "@/lib/agent-view";
import type { AgentCitation } from "@/lib/api";

import { PrivateBadge } from "./GroundingBadge";

function AchievementDetail({ id }: { id: string }) {
  const achievement = useAchievement(id);
  if (achievement.isPending) {
    return (
      <p role="status" className="text-sm text-gray-500">
        Loading the achievement…
      </p>
    );
  }
  if (achievement.isError) {
    return (
      <p role="alert" className="text-sm text-red-700">
        {achievement.error.message}
      </p>
    );
  }
  const { title, situation, task, action, result } = achievement.data;
  const rows = [
    ["Situation", situation],
    ["Task", task],
    ["Action", action],
    ["Result", result],
  ] as const;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      <dl className="flex flex-col gap-2 text-sm text-gray-700">
        {rows.map(([label, value]) =>
          value ? (
            <div key={label}>
              <dt className="text-xs font-semibold tracking-wide text-gray-500 uppercase">
                {label}
              </dt>
              <dd>{value}</dd>
            </div>
          ) : null,
        )}
      </dl>
    </div>
  );
}

export function CitationPanel({
  citation,
  onClose,
}: {
  citation: AgentCitation | null;
  onClose: () => void;
}) {
  return (
    <Drawer
      open={citation !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={citation ? citation.label : "Source"}
      description={
        citation
          ? `${KIND_LABELS[citation.kind]} — what this part of the answer rests on.`
          : undefined
      }
    >
      {citation ? (
        <>
          {citation.private ? (
            <div className="flex items-center gap-2">
              <PrivateBadge />
              <span className="text-sm text-gray-600">Generated from private repository data</span>
            </div>
          ) : null}
          {citation.kind === "achievement" && citation.achievement_id ? (
            <AchievementDetail id={citation.achievement_id} />
          ) : null}
          {citation.quote ? (
            <blockquote className="rounded-xl border-l-4 border-violet-300 bg-violet-50/60 p-3 text-sm text-gray-800">
              {citation.quote}
            </blockquote>
          ) : null}
          {citation.url ? (
            <a
              href={citation.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-semibold text-violet-700 underline underline-offset-2"
            >
              Open the source
            </a>
          ) : null}
        </>
      ) : null}
    </Drawer>
  );
}
