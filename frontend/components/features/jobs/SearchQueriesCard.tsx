"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useRegenerateQueries } from "@/hooks/use-job-search";
import type { StoredSearchQueries, StructuredProfile } from "@/lib/api";
import { useFormContext } from "react-hook-form";

import { seedSpec, type SearchFormValues } from "./search-form-schema";

function relativeAge(iso: string): string {
  const minutes = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export function isQueriesStale(
  queries: StoredSearchQueries | null | undefined,
  updatedAt: string | undefined,
): boolean {
  if (!queries || !updatedAt) return false;
  return new Date(updatedAt) > new Date(queries.generated_at);
}

export function SearchQueriesCard({
  sources,
  profileId,
  structuredProfile,
  storedQueries,
  updatedAt,
}: {
  sources: { name: string; is_official_api: boolean; supports_exclusions: boolean }[];
  profileId: string | null;
  structuredProfile: StructuredProfile | null;
  storedQueries: StoredSearchQueries | null | undefined;
  updatedAt: string | undefined;
}) {
  const form = useFormContext<SearchFormValues>();
  const regenerate = useRegenerateQueries();
  const [openSource, setOpenSource] = useState<string | null>(sources[0]?.name ?? null);
  const stale = isQueriesStale(storedQueries, updatedAt);

  const regenerateQueries = () => {
    if (profileId === null || regenerate.isPending) return;
    regenerate.mutate({ profileId });
  };

  return (
    <section className="rounded-2xl border border-gray-200 bg-gray-50/60 p-3" aria-label="Search queries">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2 px-1">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          AI search queries
        </h2>
        {profileId !== null && structuredProfile !== null && (
          <button
            type="button"
            onClick={regenerateQueries}
            disabled={regenerate.isPending}
            className="rounded-full border border-violet-300 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            {regenerate.isPending ? "Regenerating…" : "↻ Regenerate"}
          </button>
        )}
      </div>
      {stale && (
        <p role="status" className="mb-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Queries are stale — the profile changed after generation. Press Regenerate.
        </p>
      )}
      <div className="flex flex-col gap-2">
        {sources.map((source) => {
          const stored = storedQueries?.queries[source.name];
          const seed = structuredProfile !== null ? seedSpec(structuredProfile) : null;
          const seeded = seed !== null && (seed.title !== "" || seed.skills.length > 0);
          const open = openSource === source.name;
          return (
            <div key={source.name} className="rounded-xl border border-gray-200 bg-white">
              <button
                type="button"
                onClick={() => setOpenSource(open ? null : source.name)}
                aria-expanded={open}
                className="flex w-full flex-wrap items-center gap-2 px-3 py-2.5 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
              >
                <span className="text-sm font-semibold text-gray-900">{source.name}</span>
                <Badge variant={source.is_official_api ? "official-api" : "third-party-scraper"}>
                  {source.is_official_api ? "Official API" : "Third-party scraper"}
                </Badge>
                {stored === undefined && (
                  <span className="text-[11px] text-gray-500">
                    {seeded ? "seed prefilled" : "no generated query yet"}
                  </span>
                )}
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                  className={`ml-auto h-4 w-4 shrink-0 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
                >
                  <path
                    fillRule="evenodd"
                    d="M5.3 7.3a1 1 0 011.4 0L10 10.6l3.3-3.3a1 1 0 111.4 1.4l-4 4a1 1 0 01-1.4 0l-4-4a1 1 0 010-1.4z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
              {open && (
                <div className="flex flex-col gap-2.5 border-t border-gray-100 p-3">
                  <Field label="Title" htmlFor={`query-${source.name}-title`}>
                    <Input
                      id={`query-${source.name}-title`}
                      maxLength={80}
                      {...form.register(`queries.${source.name}.title`)}
                      placeholder={seed?.title || "Senior Android Engineer"}
                    />
                  </Field>
                  <Field
                    label="Skills (comma-separated)"
                    htmlFor={`query-${source.name}-skills`}
                    hint="Sent as any-of keywords where the source supports it."
                  >
                    <Input
                      id={`query-${source.name}-skills`}
                      {...form.register(`queries.${source.name}.skills`)}
                      placeholder={seed?.skills.join(", ") || "Kotlin, Java"}
                    />
                  </Field>
                  {source.supports_exclusions ? (
                    <Field
                      label="Exclude (optional, comma-separated)"
                      htmlFor={`query-${source.name}-exclude`}
                      hint="Supported by this source."
                    >
                      <Input
                        id={`query-${source.name}-exclude`}
                        {...form.register(`queries.${source.name}.exclude`)}
                        placeholder="intern"
                      />
                    </Field>
                  ) : (
                    <p className="text-xs text-gray-500">
                      This source does not support exclusions.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {storedQueries && (
        <p className="mt-2 px-1 text-[11px] text-gray-500">
          Generated {relativeAge(storedQueries.generated_at)} · {storedQueries.generated_by}
        </p>
      )}
    </section>
  );
}
