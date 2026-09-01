"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtractResume } from "@/hooks/use-upload-and-extract";
import { ApiError } from "@/lib/api";

export function DraftErrorCard({
  resumeId,
  error,
  onResolved,
}: {
  resumeId: string;
  error: Error;
  onResolved: () => void;
}) {
  const extract = useExtractResume();

  if (error instanceof ApiError && error.status === 409) {
    return (
      <Card title="Extraction didn't complete">
        <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
          This resume has no extracted draft yet — extraction failed or was interrupted.
        </p>
        {extract.error !== null && (
          <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
            {extract.error.message}
          </p>
        )}
        <Button
          disabled={extract.isPending}
          onClick={() => extract.mutate(resumeId, { onSuccess: onResolved })}
        >
          {extract.isPending ? "Extracting…" : "Extract profile"}
        </Button>
      </Card>
    );
  }

  return (
    <Card title="Could not load the extracted draft">
      <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
        {error.message}
      </p>
      <Button variant="secondary" onClick={onResolved}>
        Retry
      </Button>
    </Card>
  );
}
