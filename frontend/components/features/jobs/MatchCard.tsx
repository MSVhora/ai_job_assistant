"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import type { MatchResponse } from "@/lib/api";
import { salaryLine, scorePercent } from "@/lib/salary";

export function MatchCard({ match, rank }: { match: MatchResponse; rank: number }) {
  const [open, setOpen] = useState(false);
  const posting = match.job_posting;
  const salary = salaryLine(posting.salary_min, posting.salary_max, posting.currency);
  const detailsId = `match-rationale-${match.id}`;

  return (
    <li className="rounded-lg border border-gray-200 px-3 py-3 text-sm dark:border-gray-800">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-xs text-gray-500 dark:text-gray-400">#{rank}</span>
        <Badge variant={posting.source.startsWith("apify") ? "third-party-scraper" : "official-api"}>
          {posting.source}
        </Badge>
        {posting.url ? (
          <a
            href={posting.url}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
          >
            {posting.title}
          </a>
        ) : (
          <span className="font-medium text-gray-900 dark:text-gray-100">{posting.title}</span>
        )}
        {posting.company && <span className="text-gray-700 dark:text-gray-300">{posting.company}</span>}
        {posting.location && <span className="text-gray-500 dark:text-gray-400">{posting.location}</span>}
        {salary && <span className="text-gray-700 dark:text-gray-300">{salary}</span>}
        <span className="ml-auto flex items-center gap-3">
          {posting.posted_at && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {new Date(posting.posted_at).toLocaleDateString()}
            </span>
          )}
          <span
            className="rounded-full border border-sky-300 bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-800 dark:border-sky-700 dark:bg-sky-950 dark:text-sky-300"
            title={`Vector ${scorePercent(match.vector_score)}${match.role_fit !== null && match.role_fit !== undefined ? ` · role fit ${match.role_fit}/10` : ""}${match.company_fit !== null && match.company_fit !== undefined ? ` · company fit ${match.company_fit}/10` : ""}`}
          >
            {scorePercent(match.final_score)} match
          </span>
          {match.rationale && (
            <button
              type="button"
              aria-expanded={open}
              aria-controls={detailsId}
              onClick={() => setOpen((value) => !value)}
              className="rounded-lg px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-gray-400 dark:hover:bg-gray-800"
            >
              {open ? "Hide why" : "Why this matches"}
            </button>
          )}
        </span>
      </div>
      {open && match.rationale && (
        <p id={detailsId} className="mt-2 text-gray-700 dark:text-gray-300">
          <span className="font-medium">Why this matches: </span>
          {match.rationale}
        </p>
      )}
    </li>
  );
}
