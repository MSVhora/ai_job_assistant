"use client";

import { useState, type SyntheticEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCreateNote } from "@/hooks/use-evidence-sources";

export function NoteForm() {
  const create = useCreateNote();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    if (body.trim() === "") return;
    create.mutate(
      { title: title.trim() === "" ? null : title.trim(), body: body.trim() },
      {
        onSuccess: () => {
          setTitle("");
          setBody("");
          toast.success("Note added");
        },
      },
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" aria-label="Add a note">
      <Field label="Note title (optional)" htmlFor="note-title">
        <Input
          id="note-title"
          value={title}
          maxLength={200}
          onChange={(event) => {
            setTitle(event.target.value);
          }}
        />
      </Field>
      <Field
        label="What did you do?"
        htmlFor="note-body"
        hint="Describe work that is not in GitHub: what you built, why, and what changed."
      >
        <Textarea
          id="note-body"
          rows={4}
          value={body}
          maxLength={20000}
          onChange={(event) => {
            setBody(event.target.value);
          }}
        />
      </Field>
      <div>
        <Button type="submit" disabled={create.isPending || body.trim() === ""}>
          Add note
        </Button>
      </div>
    </form>
  );
}
