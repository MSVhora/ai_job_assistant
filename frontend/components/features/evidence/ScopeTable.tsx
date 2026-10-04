"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Card } from "@/components/ui/card";
import {
  useEmployers,
  useGithubScopes,
  useRefreshScopes,
  useUpdateScopes,
} from "@/hooks/use-evidence-sync";
import type { EvidenceStatus } from "@/lib/api";
import {
  changeCount,
  contributedCount,
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
import { ScopeRefreshBar } from "./ScopeRefreshBar";
import { ScopeStates } from "./ScopeStates";
import { ScopeRow } from "./ScopeRow";
import { ScopeSaveBar } from "./ScopeSaveBar";
import { ScopeToolbar } from "./ScopeToolbar";

export function ScopeTable({ status }: { status: EvidenceStatus }) {
  const scopes = useGithubScopes(status.configured);
  const employers = useEmployers();
  const update = useUpdateScopes();
  const refresh = useRefreshScopes();
  const { mutate: refreshScopes } = refresh;
  const autoRefreshed = useRef(false);
  const [draft, setDraft] = useState<ScopeDraft>({});
  const [query, setQuery] = useState("");
  const [onlyContributed, setOnlyContributed] = useState(false);
  const [confirming, setConfirming] = useState<string[]>([]);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(SCOPE_PAGE_SIZES[0]);

  useEffect(() => {
    if (status.configured && status.scopes_refreshed_at == null && !autoRefreshed.current) {
      autoRefreshed.current = true;
      refreshScopes();
    }
  }, [status.configured, status.scopes_refreshed_at, refreshScopes]);

  const all = scopes.data ?? [];
  const matching = filterScopes(all, query, onlyContributed);
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
        status.configured && (
          <ScopeRefreshBar
            refreshedAt={status.scopes_refreshed_at}
            pending={refresh.isPending}
            error={refresh.error}
            onRefresh={() => {
              refreshScopes();
            }}
          />
        )
      }
    >
      <ScopeStates
        configured={status.configured}
        pending={scopes.isPending}
        failed={scopes.isError}
        empty={scopes.isSuccess && all.length === 0 && !refresh.isPending}
        neverRefreshed={status.scopes_refreshed_at == null}
        onRetry={() => void scopes.refetch()}
      />
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
            contributed={contributedCount(all)}
            onlyContributed={onlyContributed}
            onToggleContributed={(only) => {
              setOnlyContributed(only);
              setPage(0);
            }}
            onSelectContributed={() => {
              setDraft((current) =>
                selectScopes(
                  current,
                  all.filter((scope) => scope.contributed),
                  true,
                ),
              );
            }}
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
