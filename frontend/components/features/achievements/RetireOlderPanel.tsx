"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useArchiveOlderVersion, useOlderVersion } from "@/hooks/use-achievements";

export function RetireOlderPanel() {
  const preview = useOlderVersion(true);
  const archive = useArchiveOlderVersion();
  const [open, setOpen] = useState(false);
  const data = preview.data;
  if (data === undefined || data.would_archive === 0) return null;

  const confirm = () => {
    archive.mutate(undefined, {
      onSuccess: (result) => {
        toast.success(`${result.archived} older achievements archived`);
        setOpen(false);
      },
    });
  };

  return (
    <section
      aria-label="Replace older extractions"
      className="flex flex-col gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
    >
      <p>
        <strong>{data.would_archive}</strong> approved achievements came from an older extraction
        and their source has since been re-extracted. Approve the new drafts you want first, then
        archive the older ones.
        {data.kept_edited > 0 && ` ${data.kept_edited} you edited are always kept.`}
        {data.kept_not_reextracted > 0 &&
          ` ${data.kept_not_reextracted} whose source was not re-extracted are kept.`}
      </p>
      <div>
        <Button
          variant="secondary"
          onClick={() => {
            setOpen(true);
          }}
        >
          Archive {data.would_archive} older…
        </Button>
      </div>
      <Modal
        open={open}
        onOpenChange={setOpen}
        title="Archive older achievements?"
        description="They move to Archived and are no longer used for resumes or the interview agent. This cannot be undone from the app; each one keeps a revision noting why."
      >
        <p className="text-sm text-gray-800">
          Archive <strong>{data.would_archive}</strong> approved achievements from older extraction
          versions?
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setOpen(false);
            }}
          >
            Cancel
          </Button>
          <Button disabled={archive.isPending} onClick={confirm}>
            Archive {data.would_archive}
          </Button>
        </div>
      </Modal>
    </section>
  );
}
