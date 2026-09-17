"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { FreshnessBadge } from "@/components/features/jobs/FreshnessBadge";
import { getJobPosting, type MatchResponse } from "@/lib/api";
import { salaryLine, scorePercent } from "@/lib/salary";

function SparkleIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3.5 w-3.5">
      <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5zM15.5 13l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4">
      <path d="M6.3 5a1 1 0 00-1.3 1.3L8.6 10l-3.6 3.7A1 1 0 006.3 15L10 11.4 13.7 15a1 1 0 001.3-1.3L11.4 10 15 6.3A1 1 0 0013.7 5L10 8.6 6.3 5z" />
    </svg>
  );
}

const JOB_TYPE_LABELS: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
  temporary: "Temporary",
};

const REMOTE_TYPE_LABELS: Record<string, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  on_site: "On-site",
};

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-gray-50/80 px-3 py-2">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span className="text-gray-600">{label}</span>
      <span className="font-semibold text-gray-900">{value}</span>
    </div>
  );
}

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
    queryFn: () => getJobPosting(matchId as string),
    enabled: matchId !== null,
    staleTime: 60_000,
  });

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
          Click any job in the list to see its full details, AI match breakdown and apply link
          here.
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
                  <Badge variant={posting.source.startsWith("apify") ? "third-party-scraper" : "official-api"}>
                    {posting.source}
                  </Badge>
                  {posting.job_type && (
                    <Badge variant="neutral">{JOB_TYPE_LABELS[posting.job_type] ?? posting.job_type}</Badge>
                  )}
                  {posting.remote_type && (
                    <Badge variant="ai">{REMOTE_TYPE_LABELS[posting.remote_type] ?? posting.remote_type}</Badge>
                  )}
                  <FreshnessBadge expiresAt={posting.expires_at} postedAt={posting.posted_at} />
                </div>
                <h3 className="mt-2 text-xl font-bold leading-snug tracking-tight text-gray-900">
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
                  value={salaryLine(posting.salary_min, posting.salary_max, posting.currency) ?? "Not disclosed"}
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
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Description
                </h4>
                {posting.description ? (
                  <p className="whitespace-pre-wrap rounded-2xl border border-gray-100 bg-gray-50/60 p-4 text-sm leading-relaxed text-gray-700">
                    {posting.description}
                  </p>
                ) : (
                  <p className="rounded-2xl border border-dashed border-gray-200 p-4 text-sm text-gray-500">
                    The source did not provide a description for this posting.
                  </p>
                )}
              </div>

              <div className="rounded-2xl border border-violet-100 bg-violet-50/50 p-4">
                <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-violet-700">
                  <SparkleIcon />
                  AI match breakdown
                </h4>
                <div className="flex flex-col gap-1.5">
                  <ScoreRow label="Final score" value={scorePercent(match?.final_score ?? 0)} />
                  <ScoreRow label="Similarity" value={scorePercent(match?.vector_score ?? 0)} />
                  {match?.role_fit != null && (
                    <ScoreRow label="Role fit" value={`${match.role_fit}/10`} />
                  )}
                  {match?.company_fit != null && (
                    <ScoreRow label="Company fit" value={`${match.company_fit}/10`} />
                  )}
                </div>
                {match?.rationale && (
                  <p className="mt-3 rounded-xl border border-violet-100 bg-white px-3 py-2.5 text-sm leading-relaxed text-gray-700">
                    {match.rationale}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {posting?.url && (
          <div className="border-t border-gray-100 p-4">
            <a
              href={posting.url}
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
