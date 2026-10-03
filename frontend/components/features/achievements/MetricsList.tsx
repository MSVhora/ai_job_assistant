"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfirmMetric } from "@/hooks/use-achievements";
import type { Achievement } from "@/lib/api";
import { metricViews, type MetricView } from "@/lib/achievement-view";

function MetricRow({ achievementId, metric }: { achievementId: string; metric: MetricView }) {
  const confirm = useConfirmMetric();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(metric.text);
  const pending = metric.verified === "needs_confirmation";

  return (
    <li className="rounded-xl border border-gray-200 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {editing ? (
          <Input
            aria-label="Metric value"
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
            }}
            className="max-w-sm"
          />
        ) : (
          <p className="text-sm font-semibold text-gray-900">{metric.text || "(empty)"}</p>
        )}
        <Badge variant={pending ? "warn" : "success"}>
          {metric.verified === "evidence"
            ? "Verified in the evidence"
            : metric.verified === "user"
              ? "Confirmed by you"
              : "Needs your confirmation"}
        </Badge>
      </div>
      {metric.sourceQuote !== null && (
        <p className="mt-1 text-xs text-gray-600">Quoted: “{metric.sourceQuote}”</p>
      )}
      {pending && (
        <p className="mt-1 text-xs text-amber-800">
          Not found verbatim in the evidence. Confirm it only if you know it is true.
        </p>
      )}
      {pending && (
        <div className="mt-2 flex flex-wrap gap-2">
          {editing ? (
            <Button
              disabled={confirm.isPending || value.trim() === ""}
              onClick={() => {
                confirm.mutate(
                  {
                    id: achievementId,
                    payload: { index: metric.index, mode: "edit", text: value.trim() },
                  },
                  {
                    onSuccess: () => {
                      setEditing(false);
                    },
                  },
                );
              }}
            >
              Confirm edited value
            </Button>
          ) : (
            <>
              <Button
                disabled={confirm.isPending}
                onClick={() => {
                  confirm.mutate({
                    id: achievementId,
                    payload: { index: metric.index, mode: "as_written" },
                  });
                }}
              >
                Confirm as written
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setEditing(true);
                }}
              >
                Edit value
              </Button>
            </>
          )}
        </div>
      )}
    </li>
  );
}

export function MetricsList({ achievement }: { achievement: Achievement }) {
  const metrics = metricViews(achievement);
  if (metrics.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No metrics. Numbers are only kept when they appear in the evidence or you confirm them.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2" aria-label="Metrics">
      {metrics.map((metric) => (
        <MetricRow
          key={`${String(metric.index)}-${metric.text}`}
          achievementId={achievement.id}
          metric={metric}
        />
      ))}
    </ul>
  );
}
