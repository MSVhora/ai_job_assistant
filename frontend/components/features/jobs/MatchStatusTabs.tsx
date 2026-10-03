export type MatchStatus = "active" | "saved" | "dismissed" | "all";

export function MatchStatusTabs({
  status,
  onChange,
}: {
  status: MatchStatus;
  onChange: (status: MatchStatus) => void;
}) {
  return (
    <nav
      aria-label="Match views"
      className="flex gap-1.5 border-b border-gray-100 px-5 pb-3 sm:px-6"
    >
      {(
        [
          ["active", "Active"],
          ["saved", "Saved"],
          ["dismissed", "Dismissed"],
          ["all", "All"],
        ] as const
      ).map(([value, label]) => (
        <button
          key={value}
          type="button"
          onClick={() => {
            onChange(value);
          }}
          aria-pressed={status === value}
          className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 ${
            status === value
              ? "bg-violet-600 text-white shadow-sm"
              : "text-gray-500 hover:bg-violet-50 hover:text-violet-700"
          }`}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}
