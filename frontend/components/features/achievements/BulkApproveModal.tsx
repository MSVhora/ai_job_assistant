"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useBulkApprove, useBulkEligible } from "@/hooks/use-achievements";

export function BulkApproveModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const eligible = useBulkEligible(open);
  const approve = useBulkApprove();
  const [unticked, setUnticked] = useState<Set<string>>(new Set());
  const items = eligible.data?.items ?? [];
  const chosen = items.filter((item) => !unticked.has(item.id));

  const confirm = () => {
    approve.mutate(
      chosen.map((item) => item.id),
      {
        onSuccess: (result) => {
          toast.success(
            `${result.approved.length} approved${
              result.skipped.length > 0 ? `, ${result.skipped.length} skipped` : ""
            }`,
          );
          onClose();
        },
      },
    );
  };

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title="Approve all fully-evidenced"
      description="Only clean drafts are listed. Private-derived, flagged, stale or unconfirmed ones always need an individual look."
    >
      {eligible.isPending && <p className="text-sm text-gray-500">Checking drafts…</p>}
      {eligible.isSuccess && items.length === 0 && (
        <p className="text-sm text-gray-600">No draft qualifies for bulk approval right now.</p>
      )}
      {items.length > 0 && (
        <ul className="flex max-h-72 flex-col gap-1.5 overflow-y-auto" aria-label="Eligible drafts">
          {items.map((item) => (
            <li key={item.id}>
              <label className="flex items-center gap-2 text-sm text-gray-800">
                <input
                  type="checkbox"
                  checked={!unticked.has(item.id)}
                  onChange={(event) => {
                    setUnticked((current) => {
                      const next = new Set(current);
                      if (event.target.checked) next.delete(item.id);
                      else next.add(item.id);
                      return next;
                    });
                  }}
                  className="h-4 w-4 rounded border-gray-300 text-violet-600"
                />
                <span className="flex-1">{item.title}</span>
                <span className="text-xs text-gray-500">{item.evidence_count} evidence</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={chosen.length === 0 || approve.isPending} onClick={confirm}>
          Approve {chosen.length}
        </Button>
      </div>
    </Modal>
  );
}
