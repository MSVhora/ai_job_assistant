"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useExtractResume } from "@/hooks/use-upload-and-extract";
import { listResumes, type ResumeSummaryResponse } from "@/lib/api";

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-4 w-4">
      <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" />
      <path d="M14 3v5h5" />
    </svg>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const linkClasses =
  "block truncate font-semibold text-gray-900 hover:text-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600";

export function ResumeList() {
  const resumesQuery = useQuery({ queryKey: ["resumes"], queryFn: listResumes });

  if (resumesQuery.isPending) {
    return (
      <section aria-labelledby="resumes-heading" className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100">
        <h2 id="resumes-heading" className="text-lg font-bold tracking-tight text-gray-900">Uploaded resumes</h2>
        <div className="mt-4 h-16 animate-pulse rounded-lg bg-gray-200" aria-live="polite" />
      </section>
    );
  }

  if (resumesQuery.isError) {
    return (
      <section aria-labelledby="resumes-heading" className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100">
        <h2 id="resumes-heading" className="text-lg font-bold tracking-tight text-gray-900">Uploaded resumes</h2>
        <p role="alert" className="mt-4 mb-3 text-sm text-red-700">
          {resumesQuery.error.message}
        </p>
        <Button variant="secondary" onClick={() => void resumesQuery.refetch()}>
          Retry
        </Button>
      </section>
    );
  }

  const resumes = resumesQuery.data;

  if (resumes.length === 0) {
    return (
      <section aria-labelledby="resumes-heading" className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100">
        <h2 id="resumes-heading" className="text-lg font-bold tracking-tight text-gray-900">Uploaded resumes</h2>
        <p className="mt-2 text-sm text-gray-600">No resumes yet — upload one above to get started.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="resumes-heading" className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 id="resumes-heading" className="text-lg font-bold tracking-tight text-gray-900">Uploaded resumes</h2>
        <Badge variant="neutral">{resumes.length}</Badge>
      </div>
      <p className="mb-4 text-sm text-gray-600">
        Click a resume to review its AI draft — merge it into an existing profile or save it as a new one. A resume without a draft can be re-extracted.
      </p>
      <ul className="flex flex-col gap-3">
        {resumes.map((resume) => (
          <ResumeRow key={resume.resume_id} resume={resume} />
        ))}
      </ul>
    </section>
  );
}

function ResumeRow({ resume }: { resume: ResumeSummaryResponse }) {
  const extract = useExtractResume();

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-100 bg-gray-50/60 p-4 transition-colors hover:border-violet-200 hover:bg-violet-50/40">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-600">
          <FileIcon />
        </span>
        <div className="min-w-0">
          {resume.has_draft ? (
            <Link href={`/profile?resume=${resume.resume_id}`} className={linkClasses}>
              {resume.original_filename}
            </Link>
          ) : (
            <span className="block truncate font-semibold text-gray-900">{resume.original_filename}</span>
          )}
          <span className="block truncate text-xs text-gray-500">
            {formatSize(resume.size_bytes)} · uploaded {new Date(resume.created_at).toLocaleString()}
          </span>
          {extract.isError && (
            <p role="alert" className="text-sm text-red-700">
              {extract.error.message}
            </p>
          )}
        </div>
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
            className="rounded-full px-3 py-1 text-xs"
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
