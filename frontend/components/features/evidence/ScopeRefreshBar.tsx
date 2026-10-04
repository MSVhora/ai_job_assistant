"use client";

import { Button } from "@/components/ui/button";

function whenText(refreshedAt: string | null | undefined): string {
  if (refreshedAt === null || refreshedAt === undefined) return "Not loaded from GitHub yet";
  return `Last refreshed ${new Date(refreshedAt).toLocaleString()}`;
}

export function ScopeRefreshBar({
  refreshedAt,
  pending,
  error,
  onRefresh,
}: {
  refreshedAt: string | null | undefined;
  pending: boolean;
  error: Error | null;
  onRefresh: () => void;
}) {
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">{whenText(refreshedAt)}</span>
        <Button variant="secondary" disabled={pending} onClick={onRefresh}>
          {pending ? "Refreshing…" : "Refresh from GitHub"}
        </Button>
      </div>
      <p role="status" aria-live="polite" className="text-xs text-gray-600">
        {pending ? "Asking GitHub for your repositories — this can take around ten seconds." : ""}
      </p>
      {error !== null && (
        <p role="alert" className="text-xs text-red-700">
          Could not refresh from GitHub: {error.message}
        </p>
      )}
    </div>
  );
}
