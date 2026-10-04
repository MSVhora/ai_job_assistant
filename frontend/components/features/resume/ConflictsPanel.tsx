"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useResolveConflict, useResumeConflicts } from "@/hooks/use-resume-documents";
import type { ResumeConflict } from "@/lib/api";

const SEVERITY = { error: "danger", warning: "warn", info: "neutral" } as const;

function ConflictRow({
  conflict,
  profileId,
  busy,
  onKeep,
}: {
  conflict: ResumeConflict;
  profileId: string;
  busy: boolean;
  onKeep: () => void;
}) {
  return (
    <li className="flex flex-col gap-1.5 rounded-xl border border-gray-100 p-3">
      <div className="flex items-center gap-2">
        <Badge variant={SEVERITY[conflict.severity]}>{conflict.severity}</Badge>
        <span className="text-sm text-gray-900">{conflict.message}</span>
      </div>
      <div className="flex gap-2">
        {conflict.suggested_actions.includes("edit_profile") && (
          <Link
            href={`/profile?profile=${profileId}`}
            className="rounded-full border border-violet-300 px-3 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Edit in profile
          </Link>
        )}
        {conflict.suggested_actions.includes("keep_as_is") && (
          <button
            type="button"
            disabled={busy}
            onClick={onKeep}
            className="rounded-full border border-gray-300 px-3 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:opacity-50"
          >
            Keep as is
          </button>
        )}
      </div>
    </li>
  );
}

export function ConflictsPanel({
  documentId,
  profileId,
  version,
}: {
  documentId: string;
  profileId: string;
  version: number;
}) {
  const conflicts = useResumeConflicts(documentId, version);
  const resolve = useResolveConflict(documentId);

  if (conflicts.isPending) {
    return <div className="h-16 animate-pulse rounded-xl bg-white/70" aria-busy="true" />;
  }
  if (conflicts.isError) {
    return (
      <p role="alert" className="text-sm text-red-700">
        Could not check this resume against your profile: {conflicts.error.message}
      </p>
    );
  }
  const { open, resolved, note } = conflicts.data;
  return (
    <Card
      title={<h2 className="text-lg font-semibold text-gray-900">Checks against your profile</h2>}
    >
      {open.length === 0 ? (
        <p className="text-sm text-gray-600">No open conflicts.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {open.map((conflict) => (
            <ConflictRow
              key={conflict.key}
              conflict={conflict}
              profileId={profileId}
              busy={resolve.isPending}
              onKeep={() => {
                resolve.mutate({ key: conflict.key, action: "keep_as_is" });
              }}
            />
          ))}
        </ul>
      )}
      {resolved.length > 0 && (
        <p className="mt-2 text-xs text-gray-500">{resolved.length} kept as is.</p>
      )}
      {note ? <p className="mt-2 text-xs text-gray-500">{note}</p> : null}
    </Card>
  );
}
