"use client";

import { skipToken, useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { FreshnessBadge } from "@/components/features/jobs/FreshnessBadge";
import { CloseIcon, DetailRow, JOB_TYPE_LABELS, REMOTE_TYPE_LABELS } from "./job-detail-parts";
import { MatchBreakdown } from "./MatchBreakdown";
import { SparkleIcon } from "./match-card-parts";
import { useOpenMatchSignal } from "@/hooks/use-match-signals";
import { applyMatchUrl, getJobPosting, type MatchResponse } from "@/lib/api";
import { salaryLine } from "@/lib/salary";

export function JobDetailPanel({
  match,
  onClose,
}: {
  match: MatchResponse | null;
  onClose: () => void;
}) {
  const matchId = match?.job_posting.id ?? null;
  const detail = useQuery({
    queryKey: ["job-posting", matchId],
    queryFn: matchId !== null ? () => getJobPosting(matchId) : skipToken,
    staleTime: 60_000,
  });
  const openSignal = useOpenMatchSignal();
  const openedMatchIdRef = useRef<string | null>(null);

  useEffect(() => {
    const id = match?.id;
    if (id === undefined || openedMatchIdRef.current === id) return;
    openedMatchIdRef.current = id;
    void openSignal(id);
  }, [match?.id, openSignal]);

  const posting = detail.data;

  if (match === null) {
    return (
      <aside
        aria-label="Job details"
        className="flex min-h-64 flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-violet-200 bg-white/70 p-8 text-center shadow-lg shadow-gray-100"
      >
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-600">
          <SparkleIcon />
        </span>
        <h2 className="text-base font-bold tracking-tight text-gray-900">Job details</h2>
        <p className="max-w-[240px] text-sm text-gray-500">
          Click any job in the list to see its full details, AI match breakdown and apply link here.
        </p>
      </aside>
    );
  }

  return (
    <aside
      aria-label="Job details"
      className="job-detail-enter flex max-h-[calc(100vh-2rem)] flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-lg shadow-gray-100"
    >
      <div className="flex items-center justify-between gap-2 border-b border-gray-100 bg-gray-50/60 px-5 py-4">
        <h2 className="flex items-center gap-2 text-base font-bold tracking-tight text-gray-900">
          <SparkleIcon />
          Job details
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close job details"
          className="rounded-full p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          <CloseIcon />
        </button>
      </div>

      <div className="scrollbar-hidden min-h-0 flex-1 overflow-y-auto p-5">
        {detail.isPending && (
          <div className="flex flex-col gap-3" aria-live="polite" aria-busy="true">
            <div className="h-6 w-3/4 animate-pulse rounded-lg bg-gray-100" />
            <div className="h-4 w-1/2 animate-pulse rounded-lg bg-gray-100" />
            <div className="h-32 animate-pulse rounded-2xl bg-gray-100" />
          </div>
        )}
        {detail.isError && (
          <div className="flex flex-col gap-3">
            <p role="alert" className="text-sm text-red-700">
              Could not load the job details: {detail.error.message}
            </p>
            <button
              type="button"
              onClick={() => void detail.refetch()}
              className="w-fit rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
            >
              Retry
            </button>
          </div>
        )}
        {posting && (
          <div className="flex flex-col gap-5">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant={
                    posting.source.startsWith("apify") ? "third-party-scraper" : "official-api"
                  }
                >
                  {posting.source}
                </Badge>
                {posting.job_type && (
                  <Badge variant="neutral">
                    {JOB_TYPE_LABELS[posting.job_type] ?? posting.job_type}
                  </Badge>
                )}
                {posting.remote_type && (
                  <Badge variant="ai">
                    {REMOTE_TYPE_LABELS[posting.remote_type] ?? posting.remote_type}
                  </Badge>
                )}
                <FreshnessBadge expiresAt={posting.expires_at} postedAt={posting.posted_at} />
              </div>
              <h3 className="mt-2 text-xl leading-snug font-bold tracking-tight text-gray-900">
                {posting.title}
              </h3>
              <p className="mt-1 text-sm text-gray-600">
                {posting.company ?? "Unknown company"}
                {posting.location && <span aria-hidden="true"> · </span>}
                {posting.location}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <DetailRow
                label="Salary"
                value={
                  salaryLine(posting.salary_min, posting.salary_max, posting.currency) ??
                  "Not disclosed"
                }
              />
              <DetailRow
                label="Posted"
                value={
                  posting.posted_at
                    ? new Date(posting.posted_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })
                    : "Unknown"
                }
              />
            </div>

            <div>
              <h4 className="mb-2 text-xs font-semibold tracking-wide text-gray-500 uppercase">
                Description
              </h4>
              {posting.description ? (
                <p className="rounded-2xl border border-gray-100 bg-gray-50/60 p-4 text-sm leading-relaxed whitespace-pre-wrap text-gray-700">
                  {posting.description}
                </p>
              ) : (
                <p className="rounded-2xl border border-dashed border-gray-200 p-4 text-sm text-gray-500">
                  The source did not provide a description for this posting.
                </p>
              )}
            </div>

            <MatchBreakdown match={match} />
          </div>
        )}
      </div>

      {posting?.url && (
        <div className="border-t border-gray-100 p-4">
          <a
            href={applyMatchUrl(match.id)}
            target="_blank"
            rel="noreferrer"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-violet-200 transition-all hover:from-violet-700 hover:to-fuchsia-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Apply Now
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4">
              <path d="M11 3a1 1 0 100 2h2.6l-3.3 3.3a1 1 0 001.4 1.4L15 6.4V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
              <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 100-2H5z" />
            </svg>
          </a>
        </div>
      )}
    </aside>
  );
}
