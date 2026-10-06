import { STARTERS } from "@/lib/agent-view";

export function StarterQuestions({
  disabled,
  onPick,
}: {
  disabled: boolean;
  onPick: (question: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-gray-600">Ask anything about your work, or try:</p>
      <ul className="flex flex-wrap gap-2">
        {STARTERS.map((starter) => (
          <li key={starter.label}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => {
                onPick(starter.question);
              }}
              className="rounded-full border border-violet-200 bg-white px-3 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {starter.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
