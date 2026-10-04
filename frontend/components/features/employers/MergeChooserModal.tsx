"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useMergeEmployers } from "@/hooks/use-employers";

/** Picks the name shown for several companies the user is merging into one employer. */
export function MergeChooserModal({ names, onClose }: { names: string[]; onClose: () => void }) {
  const merge = useMergeEmployers();
  const [canonical, setCanonical] = useState<string | null>(null);
  const shown = canonical ?? names[0] ?? "";

  const apply = () => {
    merge.mutate(
      { canonical: shown, members: names },
      {
        onSuccess: () => {
          toast.success(`Merged into ${shown}`);
          onClose();
        },
      },
    );
  };

  return (
    <Modal
      open={names.length > 0}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Merge employers"
      description="These companies will count as one employer. Choose the name to show."
    >
      <fieldset className="flex flex-col gap-1.5">
        <legend className="sr-only">Name to show</legend>
        {names.map((name) => (
          <label key={name} className="flex items-center gap-2 text-sm text-gray-800">
            <input
              type="radio"
              name="merge-canonical"
              checked={shown === name}
              onChange={() => {
                setCanonical(name);
              }}
              className="h-4 w-4 text-violet-600"
            />
            {name}
          </label>
        ))}
      </fieldset>
      {merge.isError && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {merge.error.message}
        </p>
      )}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={merge.isPending} onClick={apply}>
          {merge.isPending ? "Merging…" : "Merge"}
        </Button>
      </div>
    </Modal>
  );
}
