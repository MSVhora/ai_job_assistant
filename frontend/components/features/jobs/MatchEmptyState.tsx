import type { MatchStatus } from "./MatchStatusTabs";

export function MatchEmptyState({
  status,
  filtersActive,
  onClearFilters,
}: {
  status: MatchStatus;
  filtersActive: boolean;
  onClearFilters: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-violet-200 bg-violet-50/40 px-4 py-8 text-center">
      <p className="max-w-md text-sm text-gray-600">
        {status === "saved"
          ? "Nothing saved yet. Use Save on a match card to keep it here."
          : status === "dismissed"
            ? "No dismissed matches. Dismissed matches are hidden from the default view."
            : filtersActive
              ? "No postings match the current filters. Clear them to see every ranked match for this profile."
              : "No matches for this profile yet. Run a search to fetch postings — matches appear here when the run finishes."}
      </p>
      {filtersActive && status === "active" && (
        <button
          type="button"
          onClick={onClearFilters}
          className="rounded-full border border-violet-300 bg-white px-4 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
