"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { useEnableSource, useSources } from "@/hooks/use-setup";

import { DisclosureDialog } from "./DisclosureDialog";

export function SourceList() {
  const { data, isPending, isError, refetch } = useSources();
  const [disclosureFor, setDisclosureFor] = useState<string | null>(null);
  const enable = useEnableSource();

  if (isPending) {
    return (
      <div
        className="flex flex-col gap-3 rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur"
        aria-busy="true"
        aria-live="polite"
      >
        {[0, 1].map((index) => (
          <div
            key={index}
            className="h-14 animate-pulse rounded-2xl border border-violet-100 bg-violet-50/50"
          />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <section className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur">
        <h2 className="text-base font-bold tracking-tight text-gray-900">Job sources</h2>
        <p className="mt-2 text-sm text-red-700">
          Could not load the job sources from the backend.
        </p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="mt-3 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Retry
        </button>
      </section>
    );
  }

  return (
    <>
      <section
        className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur sm:p-8"
        aria-labelledby="job-sources-heading"
      >
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 id="job-sources-heading" className="text-base font-bold tracking-tight text-gray-900">
            Job sources
          </h2>
          <p className="text-xs text-gray-500">Where the app searches for job postings</p>
        </div>
        <ul className="flex flex-col gap-3">
          {data.map((source) => (
            <li
              key={source.name}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-violet-100 bg-violet-50/40 p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold text-gray-900">{source.name}</span>
                <Badge variant={source.is_official_api ? "official-api" : "third-party-scraper"}>
                  {source.is_official_api ? "Official API" : "Third-party scraper"}
                </Badge>
                <Badge variant={source.is_configured ? "neutral" : "warn"}>
                  {source.is_configured ? "Key ready" : "Key missing"}
                </Badge>
                {source.enabled && <Badge variant="success">Enabled</Badge>}
              </div>
              {source.disclosure_required && !source.enabled && (
                <button
                  type="button"
                  disabled={!source.is_configured}
                  onClick={() => {
                    setDisclosureFor(source.name);
                  }}
                  className="rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
                >
                  Enable…
                </button>
              )}
            </li>
          ))}
        </ul>
        {data.every((source) => !source.is_configured) && (
          <p className="mt-4 text-sm text-gray-600">
            No source keys are configured yet — add them to your backend{" "}
            <code className="rounded bg-violet-50 px-1.5 py-0.5 font-mono text-xs text-violet-700 ring-1 ring-violet-200">
              .env
            </code>
            , restart the API, then use “Re-check status” above.
          </p>
        )}
      </section>
      <DisclosureDialog
        sourceName={disclosureFor}
        pending={enable.isPending}
        onConfirm={(name) => {
          enable.mutate(
            { name, acknowledged: true },
            {
              onSettled: () => {
                setDisclosureFor(null);
              },
            },
          );
        }}
        onClose={() => {
          setDisclosureFor(null);
        }}
      />
    </>
  );
}
