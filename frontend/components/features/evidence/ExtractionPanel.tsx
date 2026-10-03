"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useChunkSummary } from "@/hooks/use-evidence-sources";
import { useEstimateExtraction, useStartExtraction } from "@/hooks/use-extraction";
import type { ExtractionEstimate } from "@/lib/api";

import { ExtractionBanner } from "./ExtractionBanner";
import { ExtractionEstimateModal } from "./ExtractionEstimateModal";

export function ExtractionPanel() {
  const summary = useChunkSummary();
  const estimate = useEstimateExtraction();
  const start = useStartExtraction();
  const [shown, setShown] = useState<ExtractionEstimate | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const chunks = summary.data;
  return (
    <Card
      title={<h2 className="text-base font-bold text-gray-900">Achievements</h2>}
      action={
        <div className="flex gap-2">
          <Button
            disabled={estimate.isPending || (chunks?.chunks ?? 0) === 0}
            onClick={() => {
              estimate.mutate(undefined, { onSuccess: setShown });
            }}
          >
            Estimate extraction
          </Button>
          <Link
            href="/evidence/review"
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Review achievements
          </Link>
        </div>
      }
    >
      <p className="mb-3 text-sm text-gray-700">
        {chunks === undefined
          ? "Loading evidence summary…"
          : `${chunks.chunks} evidence chunks (${chunks.tokens.toLocaleString()} tokens), ${chunks.embedded} embedded${
              chunks.pending_embedding > 0 ? `, ${chunks.pending_embedding} waiting` : ""
            }. ${Math.round(chunks.private_share * 100)}% come from private repositories.`}
      </p>
      <p className="mb-3 text-xs text-gray-600">
        Extraction turns chunks into draft achievements with your LLM. You see an estimate first;
        drafts are never used until you approve them.
      </p>
      {runId !== null && <ExtractionBanner runId={runId} />}
      <ExtractionEstimateModal
        estimate={shown}
        pending={start.isPending}
        onCancel={() => {
          setShown(null);
        }}
        onConfirm={(estimateId) => {
          start.mutate(estimateId, {
            onSuccess: (response) => {
              setRunId(response.run_id);
              setShown(null);
            },
            onError: () => {
              setShown(null);
            },
          });
        }}
      />
    </Card>
  );
}
