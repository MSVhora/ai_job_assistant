"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { FreshnessBadge } from "@/components/features/jobs/FreshnessBadge";
import type { MatchResponse } from "@/lib/api";
import { salaryLine, scorePercent } from "@/lib/salary";

function SparkleIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3.5 w-3.5">
      <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5zM15.5 13l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
    </svg>
  );
}

function CompanyAvatar({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <span
      aria-hidden="true"
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-xs font-bold text-white shadow-md shadow-violet-200"
    >
      {initials || "?"}
    </span>
  );
}

export function MatchCard({
  match,
  rank,
  selected = false,
  onOpenDetails,
}: {
  match: MatchResponse;
  rank: number;
  selected?: boolean;
  onOpenDetails?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const posting = match.job_posting;
  const salary = salaryLine(posting.salary_min, posting.salary_max, posting.currency);
  const detailsId = `match-rationale-${match.id}`;

  return (
    <li
      className={`group relative rounded-2xl border bg-white p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-100 ${
        selected ? "border-violet-400 ring-2 ring-violet-200" : "border-gray-200"
      }`}
    >
      <button
        type="button"
        onClick={onOpenDetails}
        aria-expanded={selected}
        aria-label={`View details for ${posting.title} at ${posting.company ?? "unknown company"}`}
        className="flex w-full items-start gap-3 rounded-xl text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
      >
        <span
          className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 text-xs font-bold text-white shadow-md shadow-violet-200"
          aria-label={`Rank ${rank}`}
        >
          {rank}
        </span>
        <CompanyAvatar name={posting.company ?? posting.title} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="truncate font-semibold text-gray-900 group-hover:text-violet-700">
              {posting.title}
            </span>
            <Badge variant={posting.source.startsWith("apify") ? "third-party-scraper" : "official-api"}>
              {posting.source}
            </Badge>
            <FreshnessBadge expiresAt={posting.expires_at} postedAt={posting.posted_at} />
          </div>
          <p className="mt-0.5 truncate text-sm text-gray-600">
            {posting.company && <span className="font-medium text-gray-800">{posting.company}</span>}
            {posting.company && posting.location && <span aria-hidden="true"> · </span>}
            {posting.location}
            {salary && (
              <>
                <span aria-hidden="true"> · </span>
                <span className="font-medium text-gray-800">{salary}</span>
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <span
            className="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-600 px-2.5 py-1 text-xs font-bold text-white shadow-md shadow-violet-200"
            title={`Vector ${scorePercent(match.vector_score)}${match.role_fit !== null && match.role_fit !== undefined ? ` · role fit ${match.role_fit}/10` : ""}${match.company_fit !== null && match.company_fit !== undefined ? ` · company fit ${match.company_fit}/10` : ""}`}
          >
            <SparkleIcon />
            {scorePercent(match.final_score)}% match
          </span>
          {posting.posted_at && (
            <span className="text-[11px] text-gray-500">
              {new Date(posting.posted_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </button>
      <div
        className={`mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-2.5 ${
          match.rationale ? "" : "border-dashed"
        }`}
      >
        {match.rationale ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={detailsId}
            onClick={() => setOpen((value) => !value)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-semibold text-violet-700 transition-colors hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            <SparkleIcon />
            {open ? "Hide why this matches" : "Why this matches"}
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
              className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
            >
              <path
                fillRule="evenodd"
                d="M5.3 7.3a1 1 0 011.4 0L10 10.6l3.3-3.3a1 1 0 111.4 1.4l-4 4a1 1 0 01-1.4 0l-4-4a1 1 0 010-1.4z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        ) : (
          <button
            type="button"
            onClick={onOpenDetails}
            className="rounded-lg px-2 py-1 text-xs text-gray-400 transition-colors hover:text-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            No AI rationale yet — view details
          </button>
        )}
        {posting.url ? (
          <a
            href={posting.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-4 py-2 text-xs font-bold text-white shadow-md shadow-violet-200 transition-all hover:from-violet-700 hover:to-fuchsia-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Apply
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3.5 w-3.5">
              <path d="M11 3a1 1 0 100 2h2.6l-3.3 3.3a1 1 0 001.4 1.4L15 6.4V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
              <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 100-2H5z" />
            </svg>
          </a>
        ) : (
          <span className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-2 text-xs font-medium text-gray-400">
            No link available
          </span>
        )}
      </div>
      {open && match.rationale && (
        <p
          id={detailsId}
          className="mt-2 rounded-xl border border-violet-100 bg-violet-50/60 px-3 py-2.5 text-sm leading-relaxed text-gray-700"
        >
          {match.rationale}
        </p>
      )}
    </li>
  );
}
