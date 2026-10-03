"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { SyncRun } from "@/lib/api";
import { formatResumeAt, viewSync } from "@/lib/evidence-progress";

const LABELS: Record<string, string> = {
  pending: "Sync queued…",
  running: "Syncing…",
  paused: "Sync paused",
  succeeded: "Sync finished",
  failed: "Sync failed",
};

const TONES: Record<string, string> = {
  pending: "border-violet-200 bg-violet-50/80",
  running: "border-violet-200 bg-violet-50/80",
  paused: "border-amber-200 bg-amber-50/80",
  succeeded: "border-emerald-200 bg-emerald-50/80",
  failed: "border-red-200 bg-red-50/80",
};

export function SyncBanner({ run }: { run: SyncRun }) {
  const view = viewSync(run);
  const resumeTime = formatResumeAt(view.resumeAt);
  return (
    <section
      aria-label="Sync status"
      className={`rounded-2xl border p-4 ${TONES[view.status] ?? "border-gray-200 bg-white"}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p aria-live="polite" className="flex items-center gap-2 text-sm font-bold text-gray-900">
          {view.active && (
            <span
              className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-violet-600 border-t-transparent"
              aria-hidden="true"
            />
          )}
          {LABELS[view.status] ?? view.status}
          <Badge>{view.mode === "full" ? "Full re-sync" : "Refresh"}</Badge>
        </p>
        <p className="text-xs text-gray-600">
          {view.items} items · {view.requests} GitHub requests used
        </p>
      </div>
      {view.status === "paused" && (
        <p role="status" className="mt-2 text-sm text-amber-900">
          Paused{view.error !== null && ` — ${view.error}`}.
          {resumeTime !== null && ` Resumes at ${resumeTime}.`} Start a refresh to continue from
          where it stopped.
        </p>
      )}
      {view.status === "failed" && view.error !== null && (
        <p role="alert" className="mt-2 text-sm text-red-800">
          {view.error}
        </p>
      )}
      {view.scopes.length > 0 && (
        <ul className="mt-3 grid gap-1 text-xs text-gray-700 sm:grid-cols-2">
          {view.scopes.map((scope) => (
            <li key={scope.ref} className="flex justify-between gap-2">
              <span className="truncate">{scope.ref}</span>
              <span>
                {scope.status} · {scope.items}
                {scope.filtered > 0 && ` (${scope.filtered} filtered)`}
              </span>
            </li>
          ))}
        </ul>
      )}
      {view.warnings.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-amber-900">
          {view.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      {view.chunks !== null && (
        <p className="mt-2 text-xs text-gray-600">
          Chunks: {view.chunks.created} new, {view.chunks.embedded} embedded
          {view.chunks.pending > 0 && `, ${view.chunks.pending} waiting for an embedding`}.
        </p>
      )}
      {view.staleFlagged > 0 && (
        <p className="mt-2 text-xs font-semibold text-amber-900">
          {view.staleFlagged} approved achievements have updated evidence —{" "}
          <Link href="/evidence/review" className="underline">
            re-review them
          </Link>
          .
        </p>
      )}
    </section>
  );
}
