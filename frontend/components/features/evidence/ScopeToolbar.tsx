"use client";

import { Input } from "@/components/ui/input";

export function ScopeToolbar({
  total,
  matching,
  selected,
  query,
  disabled,
  onQuery,
  onSelectShown,
  onClearShown,
}: {
  total: number;
  matching: number;
  selected: number;
  query: string;
  disabled: boolean;
  onQuery: (query: string) => void;
  onSelectShown: () => void;
  onClearShown: () => void;
}) {
  const filtered = matching !== total;
  const button =
    "rounded-full border border-violet-300 px-3 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:opacity-50";
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <label htmlFor="scope-filter" className="sr-only">
        Filter repositories
      </label>
      <Input
        id="scope-filter"
        type="search"
        placeholder="Filter repositories…"
        value={query}
        className="w-56"
        onChange={(event) => {
          onQuery(event.target.value);
        }}
      />
      <button
        type="button"
        className={button}
        disabled={disabled || matching === 0}
        onClick={onSelectShown}
      >
        {filtered ? `Select all ${matching} matching` : "Select all"}
      </button>
      <button
        type="button"
        className={button}
        disabled={disabled || matching === 0}
        onClick={onClearShown}
      >
        {filtered ? `Clear ${matching} matching` : "Clear selection"}
      </button>
      <p aria-live="polite" className="ml-auto text-xs text-gray-600">
        {selected} of {total} selected
      </p>
    </div>
  );
}
