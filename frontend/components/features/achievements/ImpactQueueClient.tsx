"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAddImpact, useImpactQueue, useSkipImpact } from "@/hooks/use-achievements";
import { IMPACT_LABELS } from "@/lib/achievement-view";
import type { Achievement } from "@/lib/api";

function ImpactCard({
  achievement,
  position,
  total,
  onNotNow,
}: {
  achievement: Achievement;
  position: number;
  total: number;
  onNotNow: () => void;
}) {
  const [text, setText] = useState("");
  const add = useAddImpact();
  const skip = useSkipImpact();
  const quote = (achievement.evidence ?? []).find((link) => link.quote)?.quote;
  const busy = add.isPending || skip.isPending;
  const value = text.trim();

  return (
    <form
      className="flex flex-col gap-4 rounded-2xl border border-violet-100 bg-white p-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (value === "") return;
        add.mutate(
          { id: achievement.id, text: value },
          {
            onSuccess: () => {
              toast.success("Impact saved");
            },
          },
        );
      }}
    >
      <p className="text-xs text-gray-500">
        {position} of {total}
      </p>
      <div className="flex flex-col gap-1.5">
        <h2 className="text-lg font-semibold text-gray-900">{achievement.title}</h2>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="ai">
            {IMPACT_LABELS[achievement.impact_type] ?? achievement.impact_type}
          </Badge>
          {achievement.project_key !== null && <Badge>{achievement.project_key}</Badge>}
        </div>
        <p className="text-sm text-gray-700">{achievement.action}</p>
        {achievement.result !== null && (
          <p className="text-sm text-gray-700">Result: {achievement.result}</p>
        )}
        {quote !== undefined && (
          <blockquote className="border-l-2 border-violet-200 pl-3 text-xs text-gray-500">
            {quote}
          </blockquote>
        )}
      </div>
      <Field
        label="Measurable outcome"
        htmlFor="impact-text"
        hint="Only real numbers, for example: cut the nightly import from 42 to 9 minutes, or saved about 15 engineer-hours a week."
      >
        <Input
          id="impact-text"
          value={text}
          maxLength={200}
          onChange={(event) => {
            setText(event.target.value);
          }}
        />
      </Field>
      {(add.isError || skip.isError) && (
        <p role="alert" className="text-sm text-red-700">
          Could not save. Try again.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={value === "" || busy}>
          Save impact
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => {
            skip.mutate(achievement.id);
          }}
        >
          No number to give
        </Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={onNotNow}>
          Not now
        </Button>
      </div>
    </form>
  );
}

export function ImpactQueueClient() {
  const queue = useImpactQueue();
  const [later, setLater] = useState<ReadonlySet<string>>(new Set());

  if (queue.isPending) {
    return <div className="h-48 animate-pulse rounded-2xl bg-white/70" aria-busy="true" />;
  }
  if (queue.isError) {
    return (
      <p role="alert" className="text-sm text-red-700">
        Could not load the queue.{" "}
        <button type="button" className="underline" onClick={() => void queue.refetch()}>
          Retry
        </button>
      </p>
    );
  }
  const remaining = queue.data.items.filter((item) => !later.has(item.id));
  const current = remaining[0];
  return (
    <div aria-live="polite" className="flex flex-col gap-3">
      {current === undefined ? (
        <p className="rounded-2xl border border-violet-100 bg-white p-5 text-sm text-gray-700">
          {queue.data.items.length === 0
            ? "Nothing left: every strong achievement has a confirmed number or is marked as having none."
            : "You have gone through this batch. Reload to see the rest."}
        </p>
      ) : (
        <ImpactCard
          key={current.id}
          achievement={current}
          position={queue.data.items.length - remaining.length + 1}
          total={queue.data.items.length}
          onNotNow={() => {
            setLater((currentSet) => new Set([...currentSet, current.id]));
          }}
        />
      )}
      {queue.data.total > queue.data.items.length && (
        <p className="text-xs text-gray-500">
          Showing the top {queue.data.items.length} of {queue.data.total} without a number.
        </p>
      )}
    </div>
  );
}
