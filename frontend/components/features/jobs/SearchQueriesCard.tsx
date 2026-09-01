"use client";

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
  const stale = isQueriesStale(storedQueries, updatedAt);

  const regenerateQueries = () => {
    if (profileId === null || regenerate.isPending) return;
    regenerate.mutate({ profileId });
  };

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-medium text-gray-900 dark:text-gray-100">Search queries</h2>
        {profileId !== null && structuredProfile !== null && (
          <button
            type="button"
            onClick={regenerateQueries}
            disabled={regenerate.isPending}
            className="rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-800 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-blue-700 dark:bg-blue-950 dark:text-blue-300 dark:hover:bg-blue-900"
          >
            {regenerate.isPending ? "Regenerating…" : "↻ Regenerate"}
          </button>
        )}
      </div>
      {stale && (
        <p role="status" className="mb-3 text-sm text-amber-700 dark:text-amber-400">
          Queries are stale — the profile changed after generation. Press Regenerate.
        </p>
      )}
      <div className="flex flex-col gap-4">
        {sources.map((source) => {
          const stored = storedQueries?.queries[source.name];
          const seed = structuredProfile !== null ? seedSpec(structuredProfile) : null;
          const seeded = seed !== null && (seed.title !== "" || seed.skills.length > 0);
          return (
            <div key={source.name} className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {source.name}
                </span>
                <Badge variant={source.is_official_api ? "official-api" : "third-party-scraper"}>
                  {source.is_official_api ? "Official API" : "Third-party scraper"}
                </Badge>
                {stored === undefined && (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {seeded
                      ? "seed prefilled — Regenerate fills a generated query"
                      : "no generated query yet — Regenerate fills it"}
                  </span>
                )}
              </div>
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
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  This source does not support exclusions.
                </p>
              )}
            </div>
          );
        })}
      </div>
      {storedQueries && (
        <p className="mt-4 text-xs text-gray-500 dark:text-gray-400">
          Generated {relativeAge(storedQueries.generated_at)} · {storedQueries.generated_by}
        </p>
      )}
    </section>
  );
}
