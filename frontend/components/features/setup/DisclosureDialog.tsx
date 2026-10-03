"use client";

import { useState } from "react";

import { Modal } from "@/components/ui/modal";

const LINKEDIN_DISCLOSURE = [
  "Enabling this source runs the third-party LinkedIn jobs-scraper actor through your own Apify account, not through this app's servers.",
  "Scraping LinkedIn may violate LinkedIn's Terms of Service; you are responsible for how you use this source and for the data it returns.",
  "The actor is paid per result on your Apify plan (about $1 per 1,000 results); each search is capped at the results limit you set.",
  "Job listings returned by this source are labeled with a third-party-scraper badge everywhere they appear.",
];

export function DisclosureDialog({
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
      <ul className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
        {LINKEDIN_DISCLOSURE.map((line) => (
          <li
            key={line}
            className="flex items-start gap-2.5 text-sm leading-relaxed text-amber-900"
          >
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
            >
              <path
                fillRule="evenodd"
                d="M8.5 3.5a2 2 0 013 0l6.5 11a2 2 0 01-1.5 3h-13A2 2 0 012 14.5l6.5-11zm1.5 4.25v4a.75.75 0 001.5 0v-4a.75.75 0 00-1.5 0zM10 15.5a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
            {line}
          </li>
        ))}
      </ul>
      <label className="mt-5 flex cursor-pointer items-start gap-2.5 rounded-2xl border border-violet-100 bg-violet-50/50 p-4 text-sm font-medium text-gray-900">
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(event) => {
            setAcknowledged(event.target.checked);
          }}
          className="mt-0.5 h-4 w-4 rounded border-gray-300 accent-violet-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        />
        I have read and acknowledge the disclosure above.
      </label>
      <div className="mt-5 flex flex-col gap-2 border-t border-gray-100 pt-4 sm:flex-row-reverse">
        <button
          type="button"
          disabled={!acknowledged || pending || sourceName === null}
          onClick={() => {
            if (sourceName !== null) onConfirm(sourceName);
          }}
          className="rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-violet-300 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
        >
          {pending ? "Enabling…" : "Enable source"}
        </button>
        <button
          type="button"
          onClick={() => {
            setAcknowledged(false);
            onClose();
          }}
          className="rounded-full border border-gray-300 px-5 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Cancel
        </button>
      </div>
    </Modal>
  );
}
