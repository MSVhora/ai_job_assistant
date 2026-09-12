"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { useEnableSource, useSources } from "@/hooks/use-setup";

const LINKEDIN_DISCLOSURE = [
  "Enabling this source runs the third-party LinkedIn jobs-scraper actor through your own Apify account, not through this app's servers.",
  "Scraping LinkedIn may violate LinkedIn's Terms of Service; you are responsible for how you use this source and for the data it returns.",
  "The actor is paid per result on your Apify plan (about $1 per 1,000 results); each search is capped at the results limit you set.",
  "Job listings returned by this source are labeled with a third-party-scraper badge everywhere they appear.",
];

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

  if (isError || data === undefined) {
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
          <p className="text-xs text-gray-500">
            Where the app searches for job postings
          </p>
        </div>
        <ul className="flex flex-col gap-3">
          {data.map((source) => (
            <li
              key={source.name}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-violet-100 bg-violet-50/40 p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold text-gray-900">
                  {source.name}
                </span>
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
                  onClick={() => setDisclosureFor(source.name)}
                  className="rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-400/50 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
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
            { onSettled: () => setDisclosureFor(null) },
          );
        }}
        onClose={() => setDisclosureFor(null)}
      />
    </>
  );
}

function DisclosureDialog({
  sourceName,
  pending,
  onConfirm,
  onClose,
}: {
  sourceName: string | null;
  pending: boolean;
  onConfirm: (name: string) => void;
  onClose: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);

  return (
    <Modal
      open={sourceName !== null}
      onOpenChange={(open) => {
        if (!open) {
          setAcknowledged(false);
          onClose();
        }
      }}
      title="Before you enable this scraping source"
      description="Please read and acknowledge the terms below."
    >
      <ul className="list-disc space-y-2 pl-5 text-sm text-gray-700">
        {LINKEDIN_DISCLOSURE.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <label className="mt-4 flex items-start gap-2 text-sm text-gray-900">
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(event) => setAcknowledged(event.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-gray-300 text-violet-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        />
        I have read and acknowledge the disclosure above.
      </label>
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            setAcknowledged(false);
            onClose();
          }}
          className="rounded-full border border-gray-300 px-4 py-2 text-sm font-semibold hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={!acknowledged || pending || sourceName === null}
          onClick={() => {
            if (sourceName !== null) onConfirm(sourceName);
          }}
          className="rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-400/50 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          {pending ? "Enabling…" : "Enable source"}
        </button>
      </div>
    </Modal>
  );
}
