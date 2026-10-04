"use client";

import { Button } from "@/components/ui/button";

export function ScopeSaveBar({
  changes,
  pending,
  onSave,
  onDiscard,
}: {
  changes: number;
  pending: boolean;
  onSave: () => void;
  onDiscard: () => void;
}) {
  if (changes === 0) return null;
  return (
    <div
      role="region"
      aria-label="Unsaved repository changes"
      className="fixed bottom-4 left-1/2 z-30 flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 flex-wrap items-center justify-between gap-3 rounded-2xl border border-violet-200 bg-white/95 p-3 shadow-xl backdrop-blur"
    >
      <p aria-live="polite" className="text-sm font-medium text-gray-800">
        {changes} unsaved {changes === 1 ? "change" : "changes"}
      </p>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={pending} onClick={onDiscard}>
          Discard
        </Button>
        <Button disabled={pending} onClick={onSave}>
          {pending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </div>
  );
}
