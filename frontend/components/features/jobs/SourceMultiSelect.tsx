"use client";

import type { SourceInfo } from "@/lib/api";

function InfoIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3.5 w-3.5 shrink-0">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-13a1 1 0 100 2 1 1 0 000-2zm.75 4.5a.75.75 0 00-1.5 0v3.5a.75.75 0 001.5 0V9.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function SourceMultiSelect({
  sources,
  selected,
  onToggle,
  error,
}: {
  sources: SourceInfo[];
  selected: string[];
  onToggle: (name: string, checked: boolean) => void;
  error?: string;
}) {
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Sources
        <span
          className="group relative inline-flex"
          title="Only sources enabled in setup can be searched. Green dot = official API, amber dot = third-party scraper."
        >
          <InfoIcon />
          <span className="sr-only">
            Only sources enabled in setup can be searched. Green dot = official API, amber dot = third-party scraper.
          </span>
        </span>
      </legend>
      <div className="flex flex-wrap gap-2">
        {sources.map((source) => {
          const checked = selected.includes(source.name);
          return (
            <label
              key={source.name}
              className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-violet-600 ${
                checked
                  ? "border-violet-500 bg-violet-50 font-semibold text-violet-800"
                  : "border-gray-300 bg-white text-gray-600 hover:border-violet-300"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) => onToggle(source.name, event.target.checked)}
                className="h-3.5 w-3.5 rounded border-gray-300 accent-violet-600"
                aria-label={`Search ${source.name}`}
              />
              <span>{source.name}</span>
              <span
                aria-hidden="true"
                className={`h-1.5 w-1.5 rounded-full ${
                  source.is_official_api ? "bg-emerald-500" : "bg-amber-500"
                }`}
                title={source.is_official_api ? "Official API" : "Third-party scraper"}
              />
            </label>
          );
        })}
      </div>
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </fieldset>
  );
}
