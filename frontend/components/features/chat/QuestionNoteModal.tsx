"use client";

import { useState, type SyntheticEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Textarea } from "@/components/ui/textarea";
import { useCreateNote } from "@/hooks/use-evidence-sources";
import { noteDraftFor } from "@/lib/agent-view";

export function QuestionNoteModal({
  question,
  open,
  onOpenChange,
  onSaved,
}: {
  question: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const create = useCreateNote();
  const draft = noteDraftFor(question);
  const [title, setTitle] = useState(draft.title);
  const [body, setBody] = useState(draft.body);

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    if (body.trim() === "") return;
    create.mutate(
      { title: title.trim() === "" ? null : title.trim(), body: body.trim() },
      {
        onSuccess: () => {
          onSaved();
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Add a note"
      description="Describe what happened. Extract and approve it on the Evidence page, then ask again."
    >
      <form
        onSubmit={submit}
        className="mt-4 flex flex-col gap-3"
        aria-label="Add a note for this question"
      >
        <Field label="Note title" htmlFor="question-note-title">
          <Input
            id="question-note-title"
            value={title}
            maxLength={200}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
          />
        </Field>
        <Field label="What did you do?" htmlFor="question-note-body">
          <Textarea
            id="question-note-body"
            rows={5}
            value={body}
            maxLength={20000}
            onChange={(event) => {
              setBody(event.target.value);
            }}
          />
        </Field>
        {create.isError ? (
          <p role="alert" className="text-sm text-red-700">
            {create.error.message}
          </p>
        ) : null}
        <div>
          <Button type="submit" disabled={create.isPending || body.trim() === ""}>
            Save note
          </Button>
        </div>
      </form>
    </Modal>
  );
}
