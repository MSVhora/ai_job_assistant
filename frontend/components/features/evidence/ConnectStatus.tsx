"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { EvidenceStatus } from "@/lib/api";

export function ConnectStatus({ status }: { status: EvidenceStatus }) {
  return (
    <Card
      title={<h2 className="text-base font-bold text-gray-900">GitHub connection</h2>}
      action={
        <Badge variant={status.configured ? "success" : "warn"}>
          {status.configured ? "Token configured" : "Token missing"}
        </Badge>
      }
    >
      {status.configured ? (
        <p className="text-sm text-gray-700">
          {status.login !== null ? (
            <>
              Connected as <strong>{status.login}</strong>.{" "}
            </>
          ) : (
            "Load your repositories below to confirm the connection. "
          )}
          {status.scopes_enabled} of {status.scopes_total} repositories enabled
          {status.last_synced_at !== null &&
            `, last synced ${new Date(status.last_synced_at).toLocaleString()}`}
          .
        </p>
      ) : (
        <p className="text-sm text-gray-700">
          Add a read-only token (fine-grained, or classic for organization repositories you
          collaborate on) as <code className="font-mono">GITHUB_TOKEN</code> in the project&apos;s{" "}
          <code className="font-mono">.env</code>, then run{" "}
          <code className="font-mono">docker compose up -d --force-recreate api</code>. Notes and
          resume entries below work without GitHub. See{" "}
          <Link href="/setup" className="font-semibold text-violet-700 underline">
            Setup
          </Link>{" "}
          for the other keys.
        </p>
      )}
      {status.scopes_unmapped > 0 && (
        <p className="mt-2 text-xs text-amber-800" aria-live="polite">
          {status.scopes_unmapped} synced repositories are not mapped to an employer yet; their
          achievements are treated as projects until you map them.
        </p>
      )}
    </Card>
  );
}
