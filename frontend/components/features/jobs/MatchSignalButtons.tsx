"use client";

import { useMatchSignal } from "@/hooks/use-match-signals";

export function MatchSignalButtons({
  matchId,
  title,
  profileId,
  saved,
  dismissed,
}: {
  matchId: string;
  title: string;
  profileId: string;
  saved: boolean;
  dismissed: boolean;
}) {
  const signal = useMatchSignal(profileId);

  const send = (kind: "save" | "unsave" | "dismiss" | "undismiss") => {
    if (signal.isPending) return;
    signal.mutate({ matchId, kind });
  };

  return (
    <span className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={() => {
          send(saved ? "unsave" : "save");
        }}
        aria-pressed={saved}
        disabled={signal.isPending}
        aria-label={saved ? `Remove ${title} from saved` : `Save ${title}`}
        className={`rounded-lg px-2 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-50 ${
          saved
            ? "bg-violet-100 text-violet-700"
            : "text-gray-500 hover:bg-violet-50 hover:text-violet-700"
        }`}
      >
        {saved ? "Saved" : "Save"}
      </button>
      <button
        type="button"
        onClick={() => {
          send(dismissed ? "undismiss" : "dismiss");
        }}
        disabled={signal.isPending}
        aria-label={dismissed ? `Restore ${title} to the list` : `Dismiss ${title}`}
        className="rounded-lg px-2 py-1 text-xs font-semibold text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {dismissed ? "Restore" : "Dismiss"}
      </button>
    </span>
  );
}
