"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

import { QuestionNoteModal } from "./QuestionNoteModal";

export function NoEvidenceCard({
  content,
  question,
  onReask,
  disabled,
}: {
  content: string;
  question: string;
  onReask: (question: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
      <h3 className="text-sm font-bold text-amber-900">Not in your evidence</h3>
      <p className="text-sm text-gray-800">{content}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          onClick={() => {
            setOpen(true);
          }}
        >
          Add a note
        </Button>
        {saved ? (
          <>
            <span aria-live="polite" className="text-xs text-gray-600">
              Saved. Extract and approve it on the Evidence page, then re-ask.
            </span>
            <Button
              disabled={disabled}
              onClick={() => {
                onReask(question);
              }}
            >
              Re-ask
            </Button>
          </>
        ) : null}
      </div>
      {open ? (
        <QuestionNoteModal
          question={question}
          open={open}
          onOpenChange={setOpen}
          onSaved={() => {
            setSaved(true);
          }}
        />
      ) : null}
    </div>
  );
}
