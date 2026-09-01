"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
    <Card
      title={
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Fill missing details</h2>
      }
      action={
        missing.length > 0 ? (
          <Badge variant="warn">
            {missing.length} field{missing.length === 1 ? "" : "s"} to go
          </Badge>
        ) : complete ? (
          <Badge variant="success">All set</Badge>
        ) : undefined
      }
    >
      {idle ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            A short chat to complete your job preferences - target location, remote preference,
            salary band, seniority, and work authorization. Only missing fields are asked about;
            answers are validated before anything is saved.
          </p>
          <div>
            <Button variant="secondary" onClick={start} disabled={turn.isPending}>
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
            className="flex max-h-72 flex-col gap-2 overflow-y-auto"
          >
            {entries.map((entry, index) => (
              <div
                key={index}
                className={
                  entry.role === "user"
                    ? "self-end max-w-[85%] rounded-lg bg-blue-600 px-3 py-2 text-sm text-white"
                    : "self-start max-w-[85%] rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-900 dark:bg-gray-800 dark:text-gray-100"
                }
              >
                {entry.content}
              </div>
            ))}
            {turn.isPending && (
              <div className="self-start rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                Thinking…
              </div>
            )}
          </div>

          {turn.isError && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-400">
              {turn.error.message} Your message is back in the box - press Send to try again.
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
              <span className="text-xs text-gray-500 dark:text-gray-400">Still needed:</span>
              {missing.map((field) => (
                <Badge key={field.key}>{field.label}</Badge>
              ))}
            </div>
          )}

          {complete ? (
            <p className="text-sm text-emerald-700 dark:text-emerald-400">
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
              <Button type="submit" disabled={turn.isPending || input.trim() === ""}>
                Send
              </Button>
            </form>
          )}
        </div>
      )}
    </Card>
  );
}
