"use client";

import { useTuneEstimate } from "@/hooks/use-job-search";
import type { CostEstimate } from "@/lib/api";
import { formatUsd } from "@/lib/format-cost";

function EstimateLine({ estimate }: { estimate: CostEstimate }) {
  const tokens = estimate.prompt_tokens + estimate.completion_tokens;
  return (
    <p className="mt-1.5 text-xs text-gray-700" aria-live="polite">
      Estimated cost: ≈ {tokens.toLocaleString()} tokens
      {estimate.usd !== null && estimate.usd !== undefined
        ? `, ≈ ${formatUsd(estimate.usd)}`
        : ` — ${estimate.message ?? "cost unavailable for this model"}`}
      . Approximate; up to double if the model has to repair its answer.
    </p>
  );
}

export function TuneConfirm({
  profileId,
  onConfirm,
  onCancel,
  pending,
}: {
  profileId: string;
  onConfirm: () => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const estimate = useTuneEstimate(profileId, true);
  return (
    <div className="mb-2 rounded-xl border border-violet-200 bg-violet-50 px-3 py-2.5">
      <p className="text-xs text-gray-700">
        Tuning reads your opened, saved and dismissed matches and rewrites the query specs for
        every source with <strong>one LLM call</strong> — your API key pays. Your currently
        stored specs are shown below and are replaced.
      </p>
      {estimate.isPending && (
        <p className="mt-1.5 text-xs text-gray-500" aria-live="polite">
          Estimating cost…
        </p>
      )}
      {estimate.isError && (
        <p role="alert" className="mt-1.5 text-xs text-amber-800">
          {estimate.error instanceof Error
            ? `Couldn't estimate the cost: ${estimate.error.message}`
            : "Couldn't estimate the cost."}
        </p>
      )}
      {estimate.isSuccess && <EstimateLine estimate={estimate.data} />}
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={pending}
          className="rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3 py-1 text-xs font-semibold text-white shadow-md shadow-violet-200 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Tune my queries
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-full border border-gray-300 bg-white px-3 py-1 text-xs font-semibold text-gray-600 hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
