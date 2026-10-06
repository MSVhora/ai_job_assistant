"use client";

import type { AtsSuggestion } from "@/lib/api";

const PRIORITY_STYLE: Record<string, { label: string; bar: string; chip: string }> = {
  high: {
    label: "High priority",
    bar: "bg-red-500",
    chip: "border-red-200 bg-red-50 text-red-700",
  },
  medium: {
    label: "Medium priority",
    bar: "bg-amber-500",
    chip: "border-amber-200 bg-amber-50 text-amber-700",
  },
  low: {
    label: "Nice to have",
    bar: "bg-gray-300",
    chip: "border-gray-200 bg-gray-50 text-gray-600",
  },
};

function SuggestionCard({
  suggestion,
  index,
  isLast,
}: {
  suggestion: AtsSuggestion;
  index: number;
  isLast: boolean;
}) {
  const priority = PRIORITY_STYLE[suggestion.priority] ?? PRIORITY_STYLE.low;
  return (
    <li className="relative flex gap-4 pl-2">
      <div className="relative flex flex-col items-center">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 text-xs font-bold text-white shadow-sm">
          {index + 1}
        </span>
        {!isLast && <div className={`sticky h-full w-1 rounded-full ${priority.bar}`} />}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-semibold text-gray-900">{suggestion.title}</p>
          <span className="flex items-center gap-1.5 text-xs">
            <span className="rounded-full bg-gray-100 px-2.5 py-0.5 font-medium capitalize text-gray-600">
              {suggestion.area}
            </span>
            <span className={`rounded-full border px-2.5 py-0.5 font-semibold ${priority.chip}`}>
              {priority.label}
            </span>
          </span>
        </div>
        <p className="text-sm leading-relaxed text-gray-600">{suggestion.detail}</p>
        {suggestion.rewrite_example !== null && (
          <div className="rounded-xl border-l-4 border-violet-400 bg-violet-50/60 px-4 py-3">
            <p className="text-[10px] font-bold uppercase tracking-wider text-violet-500">
              Rewrite example
            </p>
            <p className="mt-0.5 text-sm italic text-violet-900">{suggestion.rewrite_example}</p>
          </div>
        )}
      </div>
    </li>
  );
}

export function AtsSuggestions({ suggestions }: { suggestions: AtsSuggestion[] }) {
  if (suggestions.length === 0) {
    return (
      <section className="rounded-3xl border border-emerald-200 bg-emerald-50 p-6 text-center">
        <p className="text-sm font-semibold text-emerald-800">
          Your resume aligns with this job — no change suggestions for now.
        </p>
      </section>
    );
  }
  return (
    <section className="flex flex-col gap-4 rounded-3xl border border-violet-100 bg-violet-50/50 p-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-gray-900">How to improve your score</h3>
        <span className="text-xs font-medium text-gray-500">
          ordered high → low priority
        </span>
      </div>
      <ol className="flex flex-col gap-4">
        {suggestions.map((suggestion, index) => (
          <SuggestionCard
            key={suggestion.title}
            suggestion={suggestion}
            index={index}
            isLast={index === suggestions.length - 1}
          />
        ))}
      </ol>
    </section>
  );
}
