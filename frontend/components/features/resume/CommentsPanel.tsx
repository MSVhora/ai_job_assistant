"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useApplyComments, useDeleteComment } from "@/hooks/use-resume-documents";
import type { ResumeDocument } from "@/lib/api";
import { blocksOf, blockTitle } from "@/lib/resume-view";

const STATUS_VARIANT = { open: "ai", applied: "success", rejected: "warn" } as const;

export function CommentsPanel({ document }: { document: ResumeDocument }) {
  const apply = useApplyComments(document.id);
  const remove = useDeleteComment(document.id);
  const { comments } = document;
  const openCount = comments.filter((comment) => comment.status === "open").length;
  if (comments.length === 0) return null;

  const titleOf = (blockId: string) => {
    const block = blocksOf(document).find((item) => item.id === blockId);
    return block === undefined ? "a section" : blockTitle(block);
  };

  return (
    <Card
      title={<h2 className="text-lg font-semibold text-gray-900">Comments</h2>}
      action={
        <Button
          type="button"
          disabled={openCount === 0 || apply.isPending}
          onClick={() => {
            apply.mutate(undefined);
          }}
        >
          {apply.isPending
            ? "Applying…"
            : `Apply ${String(openCount)} comment${openCount === 1 ? "" : "s"}`}
        </Button>
      }
    >
      <p className="mb-3 text-xs text-gray-600">
        Applying rewrites only the commented sections, and only where your evidence supports the
        request. Everything else stays exactly as it is.
      </p>
      <ul className="flex flex-col gap-2" aria-live="polite">
        {comments.map((comment) => (
          <li
            key={comment.id}
            className="flex flex-col gap-1 rounded-xl border border-gray-100 p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={STATUS_VARIANT[comment.status]}>{comment.status}</Badge>
              <span className="text-xs text-gray-500">{titleOf(comment.target.block_id)}</span>
              <button
                type="button"
                disabled={remove.isPending}
                aria-label={`Delete comment: ${comment.text.slice(0, 40)}`}
                className="ml-auto text-xs font-semibold text-red-700 hover:underline disabled:opacity-50"
                onClick={() => {
                  remove.mutate(comment.id);
                }}
              >
                Delete
              </button>
            </div>
            <p className="text-sm text-gray-900">{comment.text}</p>
            {comment.status === "rejected" && (
              <p className="text-xs text-amber-800">
                Not applied: {comment.reason ?? "your evidence does not support it."}{" "}
                {comment.action === "add_note" && (
                  <Link href="/evidence" className="font-semibold underline">
                    Add a note
                  </Link>
                )}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
