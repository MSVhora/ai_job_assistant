"use client";

import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { getHealth, type HealthResponse } from "@/lib/api";

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
  const healthQuery = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    meta: { silent: true },
  });

  return (
    <div aria-live="polite" className="flex flex-col items-center gap-4">
      {healthQuery.isPending && (
        <div className="h-8 w-64 animate-pulse rounded-full bg-gray-200 dark:bg-gray-800" />
      )}
      {healthQuery.isError && (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-red-700 dark:text-red-400">
            Could not reach the API: {healthQuery.error.message}
          </p>
          <Button variant="secondary" onClick={() => void healthQuery.refetch()}>
            Retry
          </Button>
        </div>
      )}
      {healthQuery.isSuccess && (
        <div className="flex flex-wrap justify-center gap-3">
          <Badge ok={healthQuery.data.database} label="Database" />
          <Badge ok={healthQuery.data.llm_configured} label="LLM key" />
        </div>
      )}
    </div>
  );
}
