"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useGapFillTurn } from "@/hooks/use-gap-fill";
import type { GapFillResponse } from "@/lib/api";

type ChatEntry = { role: "user" | "assistant"; content: string };

export function GapFillChat({
  profileId,
  onApplied,
}: {
  profileId: string;
  onApplied: (response: GapFillResponse) => void;
}) {
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [missing, setMissing] = useState<GapFillResponse["missing_fields"]>([]);
  const [applied, setApplied] = useState<GapFillResponse["applied_fields"]>([]);
  const [complete, setComplete] = useState(false);
  const [input, setInput] = useState("");
  const turn = useGapFillTurn(profileId);

  const applyTurn = (data: GapFillResponse, base: ChatEntry[]) => {
    setEntries([...base, { role: "assistant", content: data.reply }]);
    setMissing(data.missing_fields);
    setComplete(data.status === "complete");
    if (data.applied_fields.length > 0) {
      setApplied((previous) => [...previous, ...data.applied_fields]);
      onApplied(data);
    }
  };

  const start = () => {
    turn.mutate([], { onSuccess: (data) => applyTurn(data, []) });
  };

  const send = () => {
    const text = input.trim();
    if (text === "") return;
    const nextEntries: ChatEntry[] = [...entries, { role: "user", content: text }];
    const messages = [
      ...entries.map((entry) => ({ role: entry.role, content: entry.content })),
      { role: "user" as const, content: text },
    ];
    setInput("");
    setEntries(nextEntries);
    turn.mutate(messages, {
      onSuccess: (data) => applyTurn(data, nextEntries),
      onError: () => {
        setEntries(entries);
        setInput(text);
      },
    });
  };

  const idle = entries.length === 0 && !turn.isPending;

  return (
    <section
      aria-labelledby="gapfill-heading"
      className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 id="gapfill-heading" className="text-lg font-bold tracking-tight text-gray-900">
          Fill missing details
        </h2>
        {missing.length > 0 ? (
          <Badge variant="warn">
            {missing.length} field{missing.length === 1 ? "" : "s"} to go
          </Badge>
        ) : complete ? (
          <Badge variant="success">All set</Badge>
        ) : undefined}
      </div>
      {idle ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-gray-600">
            A short chat to complete your job preferences — target location, remote preference,
            salary band, seniority, and work authorization. Only missing fields are asked about;
            answers are validated before anything is saved.
          </p>
          {turn.isError && (
            <p role="alert" className="text-sm text-red-700">
              {turn.error.message} Press “Start conversation” to try again.
            </p>
          )}
          <div>
            <Button
              variant="secondary"
              className="rounded-full px-5 py-2 text-sm font-semibold"
              onClick={start}
              disabled={turn.isPending}
            >
              Start conversation
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div
            role="log"
            aria-live="polite"
            aria-label="Gap-fill conversation"
            className="flex max-h-72 flex-col gap-2 overflow-y-auto rounded-2xl border border-gray-100 bg-gray-50/60 p-3"
          >
            {entries.map((entry, index) => (
              <div
                key={index}
                className={
                  entry.role === "user"
                    ? "max-w-[85%] self-end rounded-2xl rounded-br-md bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3.5 py-2 text-sm text-white shadow-md shadow-violet-200"
                    : "max-w-[85%] self-start rounded-2xl rounded-bl-md border border-gray-100 bg-white px-3.5 py-2 text-sm text-gray-900 shadow-sm"
                }
              >
                {entry.content}
              </div>
            ))}
            {turn.isPending && (
              <div className="max-w-[85%] self-start rounded-2xl rounded-bl-md border border-gray-100 bg-white px-3.5 py-2 text-sm text-gray-500 shadow-sm">
                Thinking…
              </div>
            )}
          </div>

          {turn.isError && (
            <p role="alert" className="text-sm text-red-700">
              {turn.error.message} Your message is back in the box — press Send to try again.
            </p>
          )}

          {applied.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {applied.map((field, index) => (
                <Badge key={`${field.field}-${index}`} variant="success">
                  Saved: {field.label} → {field.value}
                </Badge>
              ))}
            </div>
          )}

          {missing.length > 0 && !complete && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-gray-500">Still needed:</span>
              {missing.map((field) => (
                <Badge key={field.key}>{field.label}</Badge>
              ))}
            </div>
          )}

          {complete ? (
            <p className="text-sm font-medium text-emerald-700">
              Every gap is filled. You can still edit these fields in the form below.
            </p>
          ) : (
            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                send();
              }}
            >
              <Input
                aria-label="Your reply"
                placeholder="Type your answer…"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                disabled={turn.isPending}
              />
              <Button
                type="submit"
                disabled={turn.isPending || input.trim() === ""}
                className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 font-semibold shadow-md shadow-violet-200 hover:from-violet-700 hover:to-fuchsia-700"
              >
                Send
              </Button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}
