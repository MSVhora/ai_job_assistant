"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
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
      <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
        {[0, 1].map((index) => (
          <div
            key={index}
            className="h-16 animate-pulse rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-800"
          />
        ))}
      </div>
    );
  }

  if (isError || data === undefined) {
    return (
      <Card title="Job sources">
        <p className="text-sm text-red-700 dark:text-red-400">
          Could not load the job sources from the backend.
        </p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
        >
          Retry
        </button>
      </Card>
    );
  }

  return (
    <>
      <Card title="Job sources">
        <ul className="flex flex-col gap-3">
          {data.map((source) => (
            <li
              key={source.name}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-800"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-gray-900 dark:text-gray-100">{source.name}</span>
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
                  className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                >
                  Enable…
                </button>
              )}
            </li>
          ))}
        </ul>
        {data.every((source) => !source.is_configured) && (
          <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">
            No source keys are configured yet — add them to your backend <code>.env</code> and
            restart the API, then reload this page.
          </p>
        )}
      </Card>
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
      <ul className="list-disc space-y-2 pl-5 text-sm text-gray-700 dark:text-gray-300">
        {LINKEDIN_DISCLOSURE.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <label className="mt-4 flex items-start gap-2 text-sm text-gray-900 dark:text-gray-100">
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(event) => setAcknowledged(event.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
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
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={!acknowledged || pending || sourceName === null}
          onClick={() => {
            if (sourceName !== null) onConfirm(sourceName);
          }}
          className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          {pending ? "Enabling…" : "Enable source"}
        </button>
      </div>
    </Modal>
  );
}
