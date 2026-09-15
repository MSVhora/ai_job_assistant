"use client";

import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useRegenerateQueries } from "@/hooks/use-job-search";
import type { SourceInfo, StoredSearchQueries, StructuredProfile } from "@/lib/api";
import { useFormContext } from "react-hook-form";

import { seedSpec, type SearchFormValues } from "./search-form-schema";

function isQueriesStale(
  queries: StoredSearchQueries | null | undefined,
  updatedAt: string | undefined,
): boolean {
  if (!queries || !updatedAt) return false;
  return new Date(updatedAt) > new Date(queries.generated_at);
}

export function SearchQueriesCard({
  source,
  profileId,
  structuredProfile,
  storedQueries,
  updatedAt,
}: {
  source: SourceInfo;
  profileId: string | null;
  structuredProfile: StructuredProfile | null;
  storedQueries: StoredSearchQueries | null | undefined;
  updatedAt: string | undefined;
}) {
  const form = useFormContext<SearchFormValues>();
  const regenerate = useRegenerateQueries();
  const stale = isQueriesStale(storedQueries, updatedAt);
  const stored = storedQueries?.queries[source.name];
  const seed = structuredProfile !== null ? seedSpec(structuredProfile) : null;

  const regenerateQueries = () => {
    if (profileId === null || regenerate.isPending) return;
    regenerate.mutate({ profileId });
  };

  return (
    <section className="rounded-2xl border border-gray-200 bg-gray-50/60 p-3" aria-label="Search query">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2 px-1">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          AI search queries
        </h2>
        {profileId !== null && structuredProfile !== null && (
          <div className="flex items-center gap-2">
            <span aria-live="polite" className="text-[11px] text-gray-500">
              {regenerate.isPending
                ? "Regenerating queries…"
                : regenerate.isSuccess
                  ? "Queries regenerated"
                  : regenerate.isError
                    ? "Regeneration failed"
                    : ""}
            </span>
            <button
              type="button"
              onClick={regenerateQueries}
              disabled={regenerate.isPending}
              className="rounded-full border border-violet-300 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
            >
              {regenerate.isPending ? "Regenerating…" : "↻ Regenerate"}
            </button>
          </div>
        )}
      </div>
      {stale && (
        <p role="status" className="mb-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Queries are stale — the profile changed after generation. Press Regenerate.
        </p>
      )}
      <div className="flex flex-col gap-2.5">
        <Field label="Title" htmlFor="query-title">
          <Input
            id="query-title"
            maxLength={80}
            {...form.register("query.title")}
            placeholder={seed?.title || "Senior Android Engineer"}
          />
        </Field>
        <Field
          label="Skills (comma-separated)"
          htmlFor="query-skills"
          hint="Sent as any-of keywords where the source supports it."
        >
          <Input
            id="query-skills"
            {...form.register("query.skills")}
            placeholder={seed?.skills.join(", ") || "Kotlin, Java"}
          />
        </Field>
        {source.supports_exclusions ? (
          <Field
            label="Exclude (optional, comma-separated)"
            htmlFor="query-exclude"
            hint="Supported by this source."
          >
            <Input
              id="query-exclude"
              {...form.register("query.exclude")}
              placeholder="intern"
            />
          </Field>
        ) : (
          <p className="text-xs text-gray-500">This source does not support exclusions.</p>
        )}
        {storedQueries && (
          <p className="px-1 text-[11px] text-gray-500">
            Generated {new Date(storedQueries.generated_at).toLocaleString()} ·{" "}
            {storedQueries.generated_by}
          </p>
        )}
        {stored === undefined && seed === null && (
          <p className="px-1 text-[11px] text-gray-500">no generated query yet</p>
        )}
      </div>
    </section>
  );
}
