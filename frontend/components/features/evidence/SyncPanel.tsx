"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { useLatestSync, useStartSync } from "@/hooks/use-evidence-sync";
import type { EvidenceStatus, SyncMode } from "@/lib/api";
import { isActiveStatus } from "@/lib/evidence-progress";

import { SyncBanner } from "./SyncBanner";

export function SyncPanel({ status }: { status: EvidenceStatus }) {
  const latest = useLatestSync();
  const start = useStartSync();
  const [confirmingFull, setConfirmingFull] = useState(false);
  const active = isActiveStatus(latest.data?.status) || start.isPending;
  const blocked = !status.configured || status.scopes_enabled === 0 || active;

  const run = (mode: SyncMode) => {
    setConfirmingFull(false);
    start.mutate(mode, {
      onSuccess: () => {
        toast.success(mode === "full" ? "Full re-sync started" : "Sync started");
      },
    });
  };

  return (
    <Card
      title={<h2 className="text-base font-bold text-gray-900">Sync</h2>}
      action={
        <div className="flex gap-2">
          <Button
            disabled={blocked}
            onClick={() => {
              run("incremental");
            }}
          >
            Sync now
          </Button>
          <Button
            variant="secondary"
            disabled={blocked}
            onClick={() => {
              setConfirmingFull(true);
            }}
          >
            Full re-sync
          </Button>
        </div>
      }
    >
      <p className="mb-3 text-xs text-gray-600">
        Sync now picks up what changed since the last sync. A sync stops before it uses up its
        GitHub request budget and continues where it left off next time.
        {status.scopes_enabled === 0 && " Enable at least one repository first."}
      </p>
      {latest.data !== undefined && latest.data !== null ? (
        <SyncBanner run={latest.data} />
      ) : (
        <p className="text-sm text-gray-500">No sync has run yet.</p>
      )}
      <Modal
        open={confirmingFull}
        onOpenChange={setConfirmingFull}
        title="Run a full re-sync?"
        description="Re-reads everything within the look-back window."
      >
        <p className="text-sm text-gray-700">
          A full re-sync resets every repository&apos;s position and reads all of its history again.
          Existing evidence is updated in place and your approved achievements are never changed;
          changed evidence only creates new drafts and flags affected approved achievements for
          re-review.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setConfirmingFull(false);
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              run("full");
            }}
          >
            Start full re-sync
          </Button>
        </div>
      </Modal>
    </Card>
  );
}
