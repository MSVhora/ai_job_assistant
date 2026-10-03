"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSplitAchievement, useUnlinkEvidence } from "@/hooks/use-achievements";
import type { Achievement } from "@/lib/api";

import { EvidenceItemView } from "./EvidenceItemView";

export function EvidencePanel({
  achievement,
  onSplit,
}: {
  achievement: Achievement;
  onSplit: (newId: string) => void;
}) {
  const unlink = useUnlinkEvidence();
  const split = useSplitAchievement();
  const links = achievement.evidence ?? [];
  const [moving, setMoving] = useState<Set<string>>(new Set());
  const [title, setTitle] = useState("");
  const canSplit = links.length > 1 && achievement.status !== "archived";

  if (links.length === 0) {
    return (
      <p className="text-sm text-amber-800">
        This achievement has no evidence yet, so it cannot be approved.
      </p>
    );
  }

  const runSplit = () => {
    split.mutate(
      {
        id: achievement.id,
        payload: {
          evidence_item_ids: [...moving],
          ...(title.trim() === "" ? {} : { title: title.trim() }),
        },
      },
      {
        onSuccess: (created) => {
          setMoving(new Set());
          setTitle("");
          toast.success("Split into a new draft");
          onSplit(created.id);
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-2" aria-label="Evidence">
        {links.map((link) => (
          <EvidenceItemView
            key={link.item_id}
            link={link}
            selectable={canSplit}
            selected={moving.has(link.item_id)}
            busy={unlink.isPending}
            onSelect={(value) => {
              setMoving((current) => {
                const next = new Set(current);
                if (value) next.add(link.item_id);
                else next.delete(link.item_id);
                return next;
              });
            }}
            onUnlink={() => {
              unlink.mutate({ id: achievement.id, itemId: link.item_id });
            }}
          />
        ))}
      </ul>
      {canSplit && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-gray-50 p-3">
          <Input
            aria-label="Title of the new achievement"
            placeholder="Title for the new achievement (optional)"
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
            className="max-w-xs"
          />
          <Button
            variant="secondary"
            disabled={split.isPending || moving.size === 0 || moving.size >= links.length}
            onClick={runSplit}
          >
            Split {moving.size} into a new achievement
          </Button>
          <p className="basis-full text-xs text-gray-500">
            Tick the evidence that belongs to a separate effort. Both achievements become drafts;
            the original keeps the rest.
          </p>
        </div>
      )}
    </div>
  );
}
