"use client";

import { useEvidenceStatus } from "@/hooks/use-evidence-sync";

import { ConnectStatus } from "./ConnectStatus";
import { ExtractionPanel } from "./ExtractionPanel";
import { NotesPanel } from "./NotesPanel";
import { ScopeTable } from "./ScopeTable";
import { SyncPanel } from "./SyncPanel";

export function EvidencePageClient() {
  const status = useEvidenceStatus();

  if (status.isPending) {
    return <div className="h-48 animate-pulse rounded-3xl bg-white/70" aria-busy="true" />;
  }
  if (status.isError) {
    return (
      <div
        role="alert"
        className="rounded-3xl border border-red-200 bg-red-50 p-5 text-sm text-red-800"
      >
        Could not load the evidence status from the backend. Make sure the API is running.
        <button
          type="button"
          onClick={() => void status.refetch()}
          className="ml-3 rounded-full border border-red-300 px-3 py-1 text-xs font-semibold hover:bg-red-100"
        >
          Retry
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-5">
      <ConnectStatus status={status.data} />
      <ScopeTable status={status.data} />
      <SyncPanel status={status.data} />
      <NotesPanel />
      <ExtractionPanel />
    </div>
  );
}
