function ChevronLeftIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4">
      <path
        fillRule="evenodd"
        d="M12.7 5.3a1 1 0 010 1.4L9.4 10l3.3 3.3a1 1 0 11-1.4 1.4l-4-4a1 1 0 010-1.4l4-4a1 1 0 011.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4">
      <path
        fillRule="evenodd"
        d="M7.3 5.3a1 1 0 000 1.4l3.3 3.3-3.3 3.3a1 1 0 101.4 1.4l4-4a1 1 0 000-1.4l-4-4a1 1 0 00-1.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function MatchPagination({
  page,
  pageCount,
  onChange,
}: {
  page: number;
  pageCount: number;
  onChange: (page: number) => void;
}) {
  return (
    <nav
      aria-label="Matches pagination"
      className="flex shrink-0 items-center justify-center gap-2 border-t border-gray-100 py-3"
    >
      <button
        type="button"
        onClick={() => {
          onChange(page - 1);
        }}
        disabled={page === 0}
        className="inline-flex items-center gap-1 rounded-full border border-gray-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-gray-700 transition-colors hover:border-violet-300 hover:text-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <ChevronLeftIcon />
        Previous
      </button>
      <span className="px-2 text-xs text-gray-500" aria-current="page">
        {page + 1} / {pageCount}
      </span>
      <button
        type="button"
        onClick={() => {
          onChange(page + 1);
        }}
        disabled={page >= pageCount - 1}
        className="inline-flex items-center gap-1 rounded-full border border-gray-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-gray-700 transition-colors hover:border-violet-300 hover:text-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Next
        <ChevronRightIcon />
      </button>
    </nav>
  );
}
