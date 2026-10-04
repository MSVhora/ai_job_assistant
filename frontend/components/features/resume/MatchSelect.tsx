"use client";

import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { DEFAULT_MATCH_FILTERS, useMatches } from "@/hooks/use-matches";

const MATCH_LIMIT = 30;

export function MatchSelect({
  profileId,
  value,
  error,
  onChange,
}: {
  profileId: string;
  value: string;
  error?: string | undefined;
  onChange: (matchId: string) => void;
}) {
  const matches = useMatches(profileId === "" ? null : profileId, {
    ...DEFAULT_MATCH_FILTERS,
    limit: MATCH_LIMIT,
    offset: 0,
    priority: undefined,
    status: undefined,
  });
  const items = matches.data?.items ?? [];
  const chosen = items.find((match) => match.id === value);

  if (matches.isError) {
    return (
      <p role="alert" className="text-sm text-red-700">
        Could not load your matches: {matches.error.message}
      </p>
    );
  }
  if (!matches.isPending && items.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-violet-200 bg-violet-50/50 p-3 text-sm text-gray-600">
        This profile has no matches yet. Run a job search first, or paste a job description instead.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <Field label="Match" htmlFor="resume-match" error={error}>
        <Select
          id="resume-match"
          value={value}
          disabled={matches.isPending}
          aria-invalid={error !== undefined}
          onChange={(event) => {
            onChange(event.target.value);
          }}
        >
          <option value="">{matches.isPending ? "Loading matches…" : "Choose a match"}</option>
          {items.map((match) => (
            <option key={match.id} value={match.id}>
              {match.job_posting.title}
              {match.job_posting.company ? ` — ${match.job_posting.company}` : ""}
            </option>
          ))}
        </Select>
      </Field>
      {chosen?.rationale ? (
        <p className="rounded-xl bg-violet-50/60 p-3 text-xs text-gray-700">
          <span className="font-semibold">Why it matched: </span>
          {chosen.rationale}
        </p>
      ) : null}
    </div>
  );
}
