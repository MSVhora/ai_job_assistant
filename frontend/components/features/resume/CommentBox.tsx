"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAddComment } from "@/hooks/use-resume-documents";
import type { CommentTarget, ResumeComment } from "@/lib/api";

const STATUS_VARIANT = { open: "ai", applied: "success", rejected: "warn" } as const;

export function CommentBox({
  documentId,
  target,
  comments,
  noun,
}: {
  documentId: string;
  target: CommentTarget;
  comments: ResumeComment[];
  noun: string;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const add = useAddComment(documentId);
  const fieldId = `comment-${target.block_id}-${target.bullet_id ?? "section"}`;

  const submit = () => {
    const trimmed = text.trim();
    if (trimmed === "") return;
    add.mutate(
      { target, text: trimmed },
      {
        onSuccess: () => {
          setText("");
          setOpen(false);
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-1.5">
      {comments.map((comment) => (
        <p key={comment.id} className="flex flex-wrap items-center gap-2 text-xs text-gray-700">
          <Badge variant={STATUS_VARIANT[comment.status]}>{comment.status}</Badge>
          <span>{comment.text}</span>
        </p>
      ))}
      {open ? (
        <div className="flex flex-col gap-2">
          <label htmlFor={fieldId} className="sr-only">
            Comment on this {noun}
          </label>
          <Textarea
            id={fieldId}
            rows={2}
            value={text}
            placeholder={`What should change in this ${noun}? It is applied only where your evidence supports it.`}
            onChange={(event) => {
              setText(event.target.value);
            }}
          />
          <div className="flex gap-2">
            <Button type="button" disabled={add.isPending || text.trim() === ""} onClick={submit}>
              Add comment
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setOpen(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => {
            setOpen(true);
          }}
          className="self-start rounded-full px-2.5 py-1 text-xs font-semibold text-gray-600 hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Comment on this {noun}
        </button>
      )}
    </div>
  );
}
