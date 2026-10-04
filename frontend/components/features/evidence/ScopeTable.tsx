"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Card } from "@/components/ui/card";
import { useEmployers, useGithubScopes, useUpdateScopes } from "@/hooks/use-evidence-sync";
import type { EvidenceStatus } from "@/lib/api";
import {
  changeCount,
  filterScopes,
  newlyEnabledPrivate,
  SCOPE_PAGE_SIZES,
  paginate,
  selectScopes,
  selectedCount,
  toUpdates,
  withPatch,
  type ScopeDraft,
} from "@/lib/scope-draft";

import { DisclosureModal } from "./DisclosureModal";
import { ScopePager } from "./ScopePager";
import { ScopeRow } from "./ScopeRow";
import { ScopeSaveBar } from "./ScopeSaveBar";
import { ScopeToolbar } from "./ScopeToolbar";

export function ScopeTable({ status }: { status: EvidenceStatus }) {
  const scopes = useGithubScopes(status.configured);
  const employers = useEmployers();
  const update = useUpdateScopes();
  const [draft, setDraft] = useState<ScopeDraft>({});
  const [query, setQuery] = useState("");
  const [confirming, setConfirming] = useState<string[]>([]);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(SCOPE_PAGE_SIZES[0]);

  const all = scopes.data ?? [];
  const matching = filterScopes(all, query);
  const slice = paginate(matching, page, pageSize);

  const save = (acknowledged: boolean) => {
    update.mutate(
      { scopes: toUpdates(draft), acknowledged },
      {
        onSuccess: () => {
          setDraft({});
          setConfirming([]);
          toast.success("Repository selection saved");
        },
      },
    );
  };

  const onSave = () => {
    const privateRepos = newlyEnabledPrivate(draft, all);
    if (privateRepos.length > 0) {
      setConfirming(privateRepos);
      return;
    }
    save(false);
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
      {scopes.isSuccess && all.length === 0 && (
        <p className="text-sm text-gray-600">No repositories found for this token.</p>
      )}
      {scopes.isSuccess && all.length > 0 && (
        <>
          <p className="mb-3 text-xs text-gray-600">
            Choose the repositories evidence is collected from. Only the ones you select are synced
            and used to build your achievements and resumes — nothing is read from the rest. Your
            choices take effect when you press <strong>Save changes</strong>. New repositories start
            unselected, and a refresh never selects anything on its own.
          </p>
          <ScopeToolbar
            total={all.length}
            matching={matching.length}
            selected={selectedCount(all, draft)}
            query={query}
            disabled={update.isPending}
            onQuery={(next) => {
              setQuery(next);
              setPage(0);
            }}
            onSelectShown={() => {
              setDraft((current) => selectScopes(current, matching, true));
            }}
            onClearShown={() => {
              setDraft((current) => selectScopes(current, matching, false));
            }}
          />
          {matching.length === 0 && (
            <p className="text-sm text-gray-600">No repository matches “{query}”.</p>
          )}
          <ul className="flex flex-col gap-2" aria-label="Repositories">
            {slice.items.map((scope) => (
              <ScopeRow
                key={scope.ref}
                scope={scope}
                patch={draft[scope.ref]}
                employers={employers.data ?? []}
                disabled={update.isPending}
                onChange={(patch) => {
                  setDraft((current) => withPatch(current, scope, patch));
                }}
              />
            ))}
          </ul>
          <ScopePager
            slice={slice}
            size={pageSize}
            onPage={setPage}
            onSize={(size) => {
              setPageSize(size);
              setPage(0);
            }}
          />
          {update.isError && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              Could not save: {update.error.message}
            </p>
          )}
          <ScopeSaveBar
            changes={changeCount(draft)}
            pending={update.isPending}
            onSave={onSave}
            onDiscard={() => {
              setDraft({});
            }}
          />
        </>
      )}
      <DisclosureModal
        repos={confirming}
        firstTime={status.acknowledged_at === null}
        pending={update.isPending}
        onConfirm={() => {
          save(true);
        }}
        onCancel={() => {
          setConfirming([]);
        }}
      />
    </Card>
  );
}
