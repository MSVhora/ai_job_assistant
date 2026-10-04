"use client";

import { Drawer } from "@/components/ui/drawer";
import { useAchievement } from "@/hooks/use-achievements";

import { ActionBar } from "./ActionBar";
import { AchievementBadges } from "./AchievementBadges";
import { EmployerEditor } from "./EmployerEditor";
import { EvidencePanel } from "./EvidencePanel";
import { MetricsList } from "./MetricsList";
import { RevisionHistory } from "./RevisionHistory";
import { StarEditor } from "./StarEditor";
import { TagsEditor } from "./TagsEditor";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h3 className="text-sm font-bold text-gray-900">{title}</h3>
      {children}
    </section>
  );
}

export function AchievementDrawer({
  achievementId,
  onClose,
  onOpen,
}: {
  achievementId: string | null;
  onClose: () => void;
  onOpen: (id: string) => void;
}) {
  const detail = useAchievement(achievementId);
  const achievement = detail.data;
  return (
    <Drawer
      open={achievementId !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={achievement?.title ?? "Achievement"}
    >
      {detail.isPending && <p className="text-sm text-gray-500">Loading…</p>}
      {detail.isError && (
        <p role="alert" className="text-sm text-red-700">
          This achievement could not be loaded.
        </p>
      )}
      {achievement !== undefined && (
        <>
          <AchievementBadges achievement={achievement} />
          <ActionBar achievement={achievement} onClose={onClose} />
          <Section title="Story (STAR)">
            <StarEditor
              key={`${achievement.id}-${achievement.updated_at}`}
              achievement={achievement}
            />
          </Section>
          <Section title="Metrics">
            <MetricsList achievement={achievement} />
          </Section>
          <Section title="Tags">
            <TagsEditor
              key={`${achievement.id}-${achievement.updated_at}`}
              achievement={achievement}
            />
          </Section>
          <Section title="Employer">
            <EmployerEditor
              key={`${achievement.id}-${achievement.updated_at}`}
              achievement={achievement}
            />
          </Section>
          <Section title="Evidence">
            <EvidencePanel achievement={achievement} onSplit={onOpen} />
          </Section>
          <Section title="History">
            <RevisionHistory achievementId={achievement.id} />
          </Section>
        </>
      )}
    </Drawer>
  );
}
