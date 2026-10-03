"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useDeleteNote, useNotes, useUpdateNote } from "@/hooks/use-evidence-sources";
import type { EvidenceItem } from "@/lib/api";

function NoteItem({ note }: { note: EvidenceItem }) {
  const update = useUpdateNote();
  const remove = useDeleteNote();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.body);

  const save = () => {
    update.mutate(
      { noteId: note.id, payload: { body: draft.trim() } },
      {
        onSuccess: () => {
          setEditing(false);
          toast.success("Note updated");
        },
      },
    );
  };

  return (
    <li className="rounded-xl border border-gray-200 bg-white p-3">
      {note.title !== null && <p className="text-sm font-semibold text-gray-900">{note.title}</p>}
      {editing ? (
        <div className="mt-1 flex flex-col gap-2">
          <Textarea
            aria-label="Edit note"
            rows={4}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
            }}
          />
          <div className="flex gap-2">
            <Button onClick={save} disabled={update.isPending || draft.trim() === ""}>
              Save
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setEditing(false);
                setDraft(note.body);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <>
          <p className="mt-1 text-sm whitespace-pre-wrap text-gray-700">{note.body}</p>
          <div className="mt-2 flex gap-3 text-xs font-semibold">
            <button
              type="button"
              className="text-violet-700 hover:underline"
              onClick={() => {
                setEditing(true);
              }}
            >
              Edit
            </button>
            <button
              type="button"
              className="text-red-700 hover:underline"
              disabled={remove.isPending}
              onClick={() => {
                remove.mutate(note.id, {
                  onSuccess: () => {
                    toast.success("Note removed");
                  },
                });
              }}
            >
              Delete
            </button>
          </div>
        </>
      )}
    </li>
  );
}

export function NoteList() {
  const notes = useNotes();
  if (notes.isPending) return <div className="h-12 animate-pulse rounded-xl bg-gray-100" />;
  if (notes.isError) {
    return (
      <p role="alert" className="text-sm text-red-700">
        Could not load your notes.
      </p>
    );
  }
  if (notes.data.items.length === 0) {
    return <p className="text-sm text-gray-500">No notes yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-2" aria-label="Notes">
      {notes.data.items.map((note) => (
        <NoteItem key={note.id} note={note} />
      ))}
    </ul>
  );
}
