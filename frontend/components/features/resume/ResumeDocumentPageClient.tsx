"use client";

import Link from "next/link";

import { Card } from "@/components/ui/card";
import { useResumeDocument } from "@/hooks/use-resume-documents";
import { ApiError } from "@/lib/api";

import { DocumentView } from "./DocumentView";

export function ResumeDocumentPageClient({ id }: { id: string }) {
  const document = useResumeDocument(id);

  if (document.isPending) {
    return (
      <div
        role="status"
        aria-label="Loading resume"
        aria-busy="true"
        className="h-64 animate-pulse rounded-3xl bg-white/70"
      />
    );
  }
  if (document.isError) {
    const missing = document.error instanceof ApiError && document.error.status === 404;
    return (
      <Card>
        <p role="alert" className="mb-3 text-sm text-red-700">
          {missing
            ? "This resume was not found."
            : `Could not load this resume: ${document.error.message}`}
        </p>
        <div className="flex gap-3 text-sm">
          {!missing && (
            <button
              type="button"
              className="font-semibold text-violet-700 underline"
              onClick={() => void document.refetch()}
            >
              Retry
            </button>
          )}
          <Link href="/resume-builder" className="font-semibold text-violet-700 underline">
            Back to your resumes
          </Link>
        </div>
      </Card>
    );
  }
  return <DocumentView document={document.data} />;
}
