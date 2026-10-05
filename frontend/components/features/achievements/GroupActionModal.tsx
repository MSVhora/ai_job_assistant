"use client";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useBulkApprove, useBulkReject } from "@/hooks/use-achievements";

export interface GroupAction {
  kind: "approve" | "reject";
  label: string;
  ids: string[];
}

const COPY = {
  approve: {
    title: "Approve clean drafts",
    description:
      "Approves only drafts that are fully evidenced, with confirmed metrics and nothing flagged. Private-derived ones are never included.",
    verb: "Approve",
    done: "approved",
  },
  reject: {
    title: "Reject drafts",
    description:
      "Moves these drafts to Rejected. They are not used anywhere, and you can restore any of them later.",
    verb: "Reject",
    done: "rejected",
  },
} as const;

export function GroupActionModal({
  action,
  onClose,
}: {
  action: GroupAction | null;
  onClose: () => void;
}) {
  const approve = useBulkApprove();
  const reject = useBulkReject();
  const pending = approve.isPending || reject.isPending;
  if (action === null) return null;
  const copy = COPY[action.kind];

  const confirm = () => {
    const report = (changed: number, skipped: number) => {
      toast.success(`${changed} ${copy.done}${skipped > 0 ? `, ${skipped} skipped` : ""}`);
      onClose();
    };
    if (action.kind === "approve") {
      approve.mutate(action.ids, {
        onSuccess: (result) => {
          report(result.approved.length, result.skipped.length);
        },
      });
    } else {
      reject.mutate(action.ids, {
        onSuccess: (result) => {
          report(result.done.length, result.skipped.length);
        },
      });
    }
  };

  return (
    <Modal
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={copy.title}
      description={copy.description}
    >
      <p className="text-sm text-gray-800">
        {copy.verb} <strong>{action.ids.length}</strong> in {action.label}?
      </p>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={action.ids.length === 0 || pending} onClick={confirm}>
          {copy.verb} {action.ids.length}
        </Button>
      </div>
    </Modal>
  );
}
