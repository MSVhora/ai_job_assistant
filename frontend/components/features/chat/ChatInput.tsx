"use client";

import type { KeyboardEvent, SyntheticEvent } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export const MAX_QUESTION_CHARS = 2000;

export function ChatInput({
  value,
  onChange,
  onSend,
  pending,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  pending: boolean;
  error: string | null;
}) {
  const canSend = !pending && value.trim() !== "";
  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    if (canSend) onSend();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSend) onSend();
    }
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2" aria-label="Ask a question">
      <label htmlFor="interview-question" className="sr-only">
        Your question
      </label>
      <Textarea
        id="interview-question"
        rows={3}
        value={value}
        maxLength={MAX_QUESTION_CHARS}
        placeholder="Ask anything about your work…"
        onChange={(event) => {
          onChange(event.target.value);
        }}
        onKeyDown={onKeyDown}
      />
      {error ? (
        <p role="alert" className="text-sm text-red-700">
          {error} Your question is still here — send it again.
        </p>
      ) : null}
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-gray-500">Enter to send, Shift+Enter for a new line.</p>
        <Button type="submit" disabled={!canSend}>
          {pending ? "Thinking…" : "Send"}
        </Button>
      </div>
    </form>
  );
}
