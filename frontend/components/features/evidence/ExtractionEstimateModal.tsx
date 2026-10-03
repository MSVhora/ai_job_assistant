"use client";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import type { ExtractionEstimate } from "@/lib/api";
import { formatUsd } from "@/lib/format-cost";

function costText(usd: number | null, message: string | null | undefined): string {
  return usd === null ? (message ?? "cost unavailable for this model") : `≈ ${formatUsd(usd)}`;
}

export function ExtractionEstimateModal({
  estimate,
  pending,
  onConfirm,
  onCancel,
}: {
  estimate: ExtractionEstimate | null;
  pending: boolean;
  onConfirm: (estimateId: string) => void;
  onCancel: () => void;
}) {
  const work = estimate !== null ? estimate.chunks_to_extract + estimate.chunks_cached : 0;
  const tokens =
    estimate !== null ? estimate.llm_cost.prompt_tokens + estimate.llm_cost.completion_tokens : 0;
  return (
    <Modal
      open={estimate !== null}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
      title="Extract achievements?"
      description="Your API key pays for this. Nothing is sent until you confirm."
    >
      {estimate !== null && (
        <div className="flex flex-col gap-3 text-sm text-gray-700">
          <ul className="list-disc pl-5">
            <li>{estimate.chunks_to_extract} chunks will be sent to your LLM provider.</li>
            <li>{estimate.chunks_cached} are already cached and cost nothing.</li>
            <li>{estimate.chunks_up_to_date} are up to date and skipped.</li>
          </ul>
          <p aria-live="polite">
            Estimated cost: ≈ {tokens.toLocaleString()} tokens,{" "}
            {costText(estimate.llm_cost.usd, estimate.llm_cost.message)} for extraction and{" "}
            {costText(estimate.embedding_cost.usd, estimate.embedding_cost.message)} for embeddings.
            Approximate and an upper bound; up to double if the model must repair an answer.
          </p>
          {estimate.private_chunks > 0 && (
            <p
              role="note"
              className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-900"
            >
              {estimate.private_chunks} of {work} chunks ({Math.round(estimate.private_share * 100)}
              %) come from private repositories. Their text will reach your LLM provider, and
              anything derived from it will be marked as private.
            </p>
          )}
          {work === 0 && <p>There is nothing new to extract.</p>}
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
            <Button
              disabled={pending || work === 0}
              onClick={() => {
                onConfirm(estimate.estimate_id);
              }}
            >
              Extract achievements
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
