"use client";

import { Select } from "@/components/ui/select";
import { SCOPE_PAGE_SIZES, type PageSlice } from "@/lib/scope-draft";

const BUTTON =
  "rounded-full border border-gray-300 px-3 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:opacity-50";

export function ScopePager({
  slice,
  size,
  onPage,
  onSize,
}: {
  slice: PageSlice<unknown>;
  size: number;
  onPage: (page: number) => void;
  onSize: (size: number) => void;
}) {
  if (slice.total <= SCOPE_PAGE_SIZES[0]) return null;
  return (
    <nav aria-label="Repository pages" className="mt-3 flex flex-wrap items-center gap-2 text-xs">
      <p aria-live="polite" className="text-gray-600">
        Showing {slice.from}–{slice.to} of {slice.total}
      </p>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <label htmlFor="scope-page-size" className="text-gray-600">
          Per page
        </label>
        <Select
          id="scope-page-size"
          value={size}
          className="w-20"
          onChange={(event) => {
            onSize(Number(event.target.value));
          }}
        >
          {SCOPE_PAGE_SIZES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
        <button
          type="button"
          className={BUTTON}
          disabled={slice.page === 0}
          onClick={() => {
            onPage(slice.page - 1);
          }}
        >
          Previous
        </button>
        <span className="text-gray-600">
          Page {slice.page + 1} of {slice.pageCount}
        </span>
        <button
          type="button"
          className={BUTTON}
          disabled={slice.page >= slice.pageCount - 1}
          onClick={() => {
            onPage(slice.page + 1);
          }}
        >
          Next
        </button>
      </div>
    </nav>
  );
}
