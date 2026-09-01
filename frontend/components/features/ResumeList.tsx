"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtractResume } from "@/hooks/use-upload-and-extract";
import { listResumes, type ResumeSummaryResponse } from "@/lib/api";

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const linkClasses =
  "font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400";

export function ResumeList() {
  const resumesQuery = useQuery({ queryKey: ["resumes"], queryFn: listResumes });

  if (resumesQuery.isPending) {
    return (
      <Card title="Uploaded resumes">
        <div className="h-16 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-800" aria-live="polite" />
      </Card>
    );
  }

  if (resumesQuery.isError) {
    return (
      <Card title="Uploaded resumes">
        <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-400">
          {resumesQuery.error.message}
        </p>
        <Button variant="secondary" onClick={() => void resumesQuery.refetch()}>
          Retry
        </Button>
      </Card>
    );
  }

  const resumes = resumesQuery.data;

  if (resumes.length === 0) {
    return (
      <Card title="Uploaded resumes">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          No resumes yet — upload one above to get started.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Uploaded resumes">
      <p className="mb-3 text-sm text-gray-600 dark:text-gray-400">
        Click a resume to review its AI draft — merge it into an existing profile or save it as
        a new one. A resume without a draft can be re-extracted.
      </p>
      <ul className="flex flex-col gap-3">
        {resumes.map((resume) => (
          <ResumeRow key={resume.resume_id} resume={resume} />
        ))}
      </ul>
    </Card>
  );
}

function ResumeRow({ resume }: { resume: ResumeSummaryResponse }) {
  const extract = useExtractResume();

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div className="flex flex-col">
        {resume.has_draft ? (
          <Link href={`/profile?resume=${resume.resume_id}`} className={linkClasses}>
            {resume.original_filename}
          </Link>
        ) : (
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {resume.original_filename}
          </span>
        )}
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {formatSize(resume.size_bytes)} · uploaded{" "}
          {new Date(resume.created_at).toLocaleString()}
        </span>
        {extract.isError && (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            {extract.error.message}
          </p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {resume.source_profile_names.map((name) => (
          <Badge key={name} variant="success">
            seeds {name}
          </Badge>
        ))}
        {resume.has_draft ? (
          <Badge variant="ai">draft ready</Badge>
        ) : (
          <Button
            variant="secondary"
            className="px-2 py-1"
            disabled={extract.isPending}
            onClick={() => extract.mutate(resume.resume_id)}
          >
            {extract.isPending ? "Extracting…" : "Extract profile"}
          </Button>
        )}
      </div>
    </li>
  );
}
