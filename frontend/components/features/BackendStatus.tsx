"use client";

import { useCallback, useEffect, useState } from "react";

import { getHealth, type HealthResponse } from "@/lib/api";

type Status =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: HealthResponse };

const badgeStyles =
  "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium";

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`${badgeStyles} ${
        ok
          ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
          : "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300"
      }`}
    >
      <span aria-hidden>{ok ? "✓" : "✗"}</span>
      {label}
    </span>
  );
}

export function BackendStatus() {
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    getHealth()
      .then((data) => {
        if (active) {
          setStatus({ kind: "ready", data });
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setStatus({
            kind: "error",
            message: cause instanceof Error ? cause.message : "Unknown error",
          });
        }
      });
    return () => {
      active = false;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setStatus({ kind: "loading" });
    setAttempt((value) => value + 1);
  }, []);

  return (
    <div aria-live="polite" className="flex flex-col items-center gap-4">
      {status.kind === "loading" && (
        <div className="h-8 w-64 animate-pulse rounded-full bg-gray-200 dark:bg-gray-800" />
      )}
      {status.kind === "error" && (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-red-700 dark:text-red-400">
            Could not reach the API: {status.message}
          </p>
          <button
            type="button"
            onClick={retry}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
          >
            Retry
          </button>
        </div>
      )}
      {status.kind === "ready" && (
        <div className="flex flex-wrap justify-center gap-3">
          <Badge ok={status.data.database} label="Database" />
          <Badge ok={status.data.llm_configured} label="LLM key" />
        </div>
      )}
    </div>
  );
}
