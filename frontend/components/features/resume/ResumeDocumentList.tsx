"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useDeleteResumeDocument, useResumeDocuments } from "@/hooks/use-resume-documents";

export function ResumeDocumentList() {
  const documents = useResumeDocuments(null);
  const remove = useDeleteResumeDocument();

  return (
    <Card title={<h2 className="text-lg font-semibold text-gray-900">Your resumes</h2>}>
      {documents.isPending && (
        <div className="h-16 animate-pulse rounded-xl bg-gray-100" aria-busy="true" />
      )}
      {documents.isError && (
        <p role="alert" className="text-sm text-red-700">
          Could not load your resumes: {documents.error.message}{" "}
          <button
            type="button"
            className="font-semibold underline"
            onClick={() => void documents.refetch()}
          >
            Retry
          </button>
        </p>
      )}
      {documents.data?.items.length === 0 && (
        <p className="text-sm text-gray-600">No resumes yet — create your first one above.</p>
      )}
      <ul className="flex flex-col divide-y divide-gray-100">
        {documents.data?.items.map((document) => (
          <li key={document.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
            <div className="flex min-w-0 flex-col">
              <Link
                href={`/resume-builder/${document.id}`}
                className="truncate text-sm font-semibold text-violet-700 underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
              >
                {document.title}
              </Link>
              <span className="text-xs text-gray-500">
                Updated {new Date(document.updated_at).toLocaleString()}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="neutral">
                {document.page_target} {document.page_target === 1 ? "page" : "pages"}
              </Badge>
              <button
                type="button"
                className="rounded-full px-3 py-1 text-xs font-semibold text-red-700 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600 disabled:opacity-50"
                disabled={remove.isPending}
                aria-label={`Delete ${document.title}`}
                onClick={() => {
                  remove.mutate(document.id);
                }}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
