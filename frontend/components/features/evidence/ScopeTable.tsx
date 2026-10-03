"use client";

import { useState } from "react";

import { Card } from "@/components/ui/card";
import { useEmployers, useGithubScopes, useUpdateScopes } from "@/hooks/use-evidence-sync";
import type { EvidenceScope, EvidenceStatus, ScopeUpdateItem } from "@/lib/api";

import { DisclosureModal } from "./DisclosureModal";
import { ScopeRow } from "./ScopeRow";

export function ScopeTable({ status }: { status: EvidenceStatus }) {
  const scopes = useGithubScopes(status.configured);
  const employers = useEmployers();
  const update = useUpdateScopes();
  const [pendingPrivate, setPendingPrivate] = useState<string | null>(null);

  const apply = (item: ScopeUpdateItem, acknowledged = false) => {
    update.mutate({ scopes: [item], acknowledged });
  };

  const toggle = (scope: EvidenceScope, enabled: boolean) => {
    if (enabled && scope.is_private) {
      setPendingPrivate(scope.ref);
      return;
    }
    apply({ ref: scope.ref, enabled });
  };

  const confirmPrivate = () => {
    if (pendingPrivate === null) return;
    apply({ ref: pendingPrivate, enabled: true }, true);
    setPendingPrivate(null);
  };

  return (
    <Card
      title={<h2 className="text-base font-bold text-gray-900">Repositories</h2>}
      action={
        scopes.isFetching && <span className="text-xs text-gray-500">Loading repositories…</span>
      }
    >
      {!status.configured && (
        <p className="text-sm text-gray-600">Connect GitHub to list your repositories.</p>
      )}
      {status.configured && scopes.isPending && (
        <div className="h-24 animate-pulse rounded-2xl bg-gray-100" aria-busy="true" />
      )}
      {scopes.isError && (
        <div role="alert" className="flex items-center justify-between gap-3 text-sm text-red-700">
          <span>Could not load your repositories. Check the token and try again.</span>
          <button
            type="button"
            onClick={() => void scopes.refetch()}
            className="rounded-full border border-red-300 px-3 py-1 text-xs font-semibold hover:bg-red-50"
          >
            Retry
          </button>
        </div>
      )}
      {scopes.isSuccess && scopes.data.length === 0 && (
        <p className="text-sm text-gray-600">No repositories found for this token.</p>
      )}
      {scopes.isSuccess && scopes.data.length > 0 && (
        <>
          <p className="mb-3 text-xs text-gray-500">
            New repositories start disabled. A refresh never enables anything on its own.
          </p>
          <ul className="flex flex-col gap-2" aria-label="Repositories">
            {scopes.data.map((scope) => (
              <ScopeRow
                key={scope.ref}
                scope={scope}
                employers={employers.data ?? []}
                disabled={update.isPending}
                onChange={(item) => {
                  apply(item);
                }}
                onToggle={toggle}
              />
            ))}
          </ul>
        </>
      )}
      <DisclosureModal
        repo={pendingPrivate}
        firstTime={status.acknowledged_at === null}
        pending={update.isPending}
        onConfirm={confirmPrivate}
        onCancel={() => {
          setPendingPrivate(null);
        }}
      />
    </Card>
  );
}
