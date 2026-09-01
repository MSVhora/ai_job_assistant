"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { SourceInfo } from "@/lib/api";

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
    <fieldset className="flex flex-col gap-1">
      <legend className="text-sm font-medium text-gray-800 dark:text-gray-200">Sources</legend>
      <div className="flex flex-col gap-2">
        {sources.map((source) => {
          const checked = selected.includes(source.name);
          return (
            <label
              key={source.name}
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-gray-200 px-3 py-2 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800"
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) => onToggle(source.name, event.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              />
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {source.name}
              </span>
              <Badge variant={source.is_official_api ? "official-api" : "third-party-scraper"}>
                {source.is_official_api ? "Official API" : "Third-party scraper"}
              </Badge>
            </label>
          );
        })}
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Only sources enabled in{" "}
        <Link
          href="/setup"
          className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
        >
          setup
        </Link>{" "}
        can be searched.
      </p>
      {error && (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </fieldset>
  );
}
