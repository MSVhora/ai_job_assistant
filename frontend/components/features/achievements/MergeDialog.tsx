"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { useMergeAchievements } from "@/hooks/use-achievements";

export interface MergeCandidate {
  id: string;
  title: string;
}

export function MergeDialog({
  candidates,
  onClose,
  onMerged,
}: {
  candidates: MergeCandidate[];
  onClose: () => void;
  onMerged: (id: string) => void;
}) {
  const merge = useMergeAchievements();
  const [title, setTitle] = useState(candidates[0]?.title ?? "");

  return (
    <Modal
      open={candidates.length >= 2}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Merge achievements"
      description="Creates one new draft with the combined evidence, skills and metrics. The originals are archived."
    >
      <ul className="mb-4 list-disc pl-5 text-sm text-gray-700">
        {candidates.map((candidate) => (
          <li key={candidate.id}>{candidate.title}</li>
        ))}
      </ul>
      <Field
        label="Title of the merged achievement"
        htmlFor="merge-title"
        hint="The story text of the first one is kept; edit it after merging."
      >
        <Input
          id="merge-title"
          value={title}
          maxLength={200}
          onChange={(event) => {
            setTitle(event.target.value);
          }}
        />
      </Field>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={merge.isPending || title.trim() === ""}
          onClick={() => {
            merge.mutate(
              { ids: candidates.map((candidate) => candidate.id), title: title.trim() },
              {
                onSuccess: (created) => {
                  toast.success("Merged into a new draft");
                  onMerged(created.id);
                },
              },
            );
          }}
        >
          Merge
        </Button>
      </div>
    </Modal>
  );
}
