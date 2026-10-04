"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import {
  useEstimateMergeSuggestions,
  useMergeEmployers,
  useSuggestMerges,
} from "@/hooks/use-employers";
import type { CostEstimate, EmployerMergeSuggestion } from "@/lib/api";
import { formatUsd } from "@/lib/format-cost";

function EstimateLine({ estimate }: { estimate: CostEstimate }) {
  const tokens = estimate.prompt_tokens + estimate.completion_tokens;
  if (tokens === 0) {
    return <p className="text-xs text-gray-700">Already answered for these employers: no cost.</p>;
  }
  return (
    <p className="text-xs text-gray-700" aria-live="polite">
      Estimated cost: ≈ {tokens.toLocaleString()} tokens
      {estimate.usd !== null
        ? `, ≈ ${formatUsd(estimate.usd)}`
        : ` — ${estimate.message ?? "cost unavailable for this model"}`}
      . Approximate.
    </p>
  );
}

function Suggestions({
  suggestions,
  onDone,
}: {
  suggestions: EmployerMergeSuggestion[];
  onDone: () => void;
}) {
  const merge = useMergeEmployers();
  const [skipped, setSkipped] = useState<ReadonlySet<string>>(new Set());
  if (suggestions.length === 0) {
    return (
      <>
        <p className="text-sm text-gray-700">No employers look like duplicates of each other.</p>
        <div className="flex justify-end">
          <Button variant="secondary" onClick={onDone}>
            Close
          </Button>
        </div>
      </>
    );
  }
  const chosen = suggestions.filter((item) => !skipped.has(item.canonical));
  const apply = async () => {
    for (const item of chosen) {
      await merge.mutateAsync({ canonical: item.canonical, members: item.members });
    }
    toast.success(`${chosen.length} merge${chosen.length === 1 ? "" : "s"} saved`);
    onDone();
  };
  return (
    <>
      <p className="text-xs text-gray-600">
        These are suggestions only. Untick any you do not agree with; nothing changes until you
        merge.
      </p>
      <ul className="flex flex-col gap-2" aria-label="Suggested merges">
        {suggestions.map((item) => (
          <li key={item.canonical} className="rounded-xl border border-gray-200 p-3 text-sm">
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={!skipped.has(item.canonical)}
                onChange={(event) => {
                  setSkipped((current) => {
                    const next = new Set(current);
                    if (event.target.checked) next.delete(item.canonical);
                    else next.add(item.canonical);
                    return next;
                  });
                }}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-violet-600"
              />
              <span>
                <span className="font-semibold text-gray-900">{item.members.join(" + ")}</span>
                <span className="text-gray-600"> → shown as {item.canonical}</span>
                {item.reason && <span className="block text-xs text-gray-600">{item.reason}</span>}
              </span>
            </label>
          </li>
        ))}
      </ul>
      {merge.isError && (
        <p role="alert" className="text-sm text-red-700">
          {merge.error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button disabled={chosen.length === 0 || merge.isPending} onClick={() => void apply()}>
          {merge.isPending ? "Merging…" : `Merge ${chosen.length} selected`}
        </Button>
      </div>
    </>
  );
}

function Body({ onDone }: { onDone: () => void }) {
  const estimate = useEstimateMergeSuggestions();
  const suggest = useSuggestMerges();
  const { mutate: runEstimate } = estimate;
  useEffect(() => {
    runEstimate();
  }, [runEstimate]);

  if (suggest.isSuccess) {
    return <Suggestions suggestions={suggest.data.suggestions} onDone={onDone} />;
  }
  const error = estimate.error ?? suggest.error;
  return (
    <>
      <p className="text-sm text-gray-700">
        This sends only your employers&apos; names to your LLM in <strong>one call</strong> and asks
        which are probably the same company. Your API key pays. You review every suggestion before
        anything is merged.
      </p>
      {estimate.isPending && <p className="text-xs text-gray-500">Estimating the cost…</p>}
      {estimate.data !== undefined && <EstimateLine estimate={estimate.data} />}
      {error !== null && (
        <p role="alert" className="text-sm text-red-700">
          {error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button
          disabled={estimate.data === undefined || suggest.isPending}
          onClick={() => {
            suggest.mutate();
          }}
        >
          {suggest.isPending ? "Asking the model…" : "Ask the model"}
        </Button>
      </div>
    </>
  );
}

export function MergeSuggestionsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title="Suggest employer merges"
    >
      {open && <Body onDone={onClose} />}
    </Modal>
  );
}
