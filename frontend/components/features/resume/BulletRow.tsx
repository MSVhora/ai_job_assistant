"use client";

import { Badge } from "@/components/ui/badge";
import { usePinBullet, useRemoveBullet } from "@/hooks/use-resume-documents";
import type { ResumeBullet, ResumeComment } from "@/lib/api";

import { CommentBox } from "./CommentBox";
import { CopyButton } from "./CopyButton";
import { EvidenceChips } from "./EvidenceChips";

const ACTION =
  "rounded-full px-2.5 py-1 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:opacity-50";

export function BulletRow({
  documentId,
  section,
  blockId,
  bullet,
  comments,
}: {
  documentId: string;
  section: "work" | "projects";
  blockId: string;
  bullet: ResumeBullet;
  comments: ResumeComment[];
}) {
  const pin = usePinBullet(documentId);
  const remove = useRemoveBullet(documentId);
  const busy = pin.isPending || remove.isPending;

  return (
    <li className="flex flex-col gap-1.5 rounded-xl border border-gray-100 bg-white p-3">
      <p className="text-sm text-gray-900 select-text">{bullet.text}</p>
      <div className="flex flex-wrap items-center gap-1.5">
        {bullet.from_private && <Badge variant="warn">Private repo</Badge>}
        {bullet.origin === "user_edited" && <Badge variant="ai">Edited by you</Badge>}
        {bullet.origin === "profile_verbatim" && <Badge>From your profile</Badge>}
        {bullet.approved_anyway && <Badge variant="warn">Approved despite a flag</Badge>}
        {bullet.pinned && <Badge variant="success">Pinned</Badge>}
        <EvidenceChips ids={bullet.evidence_ids} />
      </div>
      {bullet.approved_anyway && bullet.flags.length > 0 && (
        <p className="text-xs text-amber-800">Flagged: {bullet.flags.join("; ")}</p>
      )}
      <div className="flex flex-wrap items-center gap-1">
        <CopyButton
          label="Copy"
          ariaLabel={`Copy bullet: ${bullet.text.slice(0, 40)}`}
          getText={() => bullet.text}
        />
        <button
          type="button"
          disabled={busy}
          className={`${ACTION} text-gray-700 hover:bg-gray-100`}
          onClick={() => {
            pin.mutate({ bulletId: bullet.id, pinned: !bullet.pinned });
          }}
        >
          {bullet.pinned ? "Unpin" : "Pin"}
        </button>
        <button
          type="button"
          disabled={busy}
          className={`${ACTION} text-red-700 hover:bg-red-50`}
          onClick={() => {
            remove.mutate(bullet.id);
          }}
        >
          Remove
        </button>
      </div>
      <CommentBox
        documentId={documentId}
        target={{ section, block_id: blockId, bullet_id: bullet.id }}
        comments={comments}
        noun="bullet"
      />
    </li>
  );
}
