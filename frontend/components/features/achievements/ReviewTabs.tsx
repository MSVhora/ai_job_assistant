"use client";

import { TABS, type ReviewTab } from "./review-tabs";

export function ReviewTabs({
  active,
  onChange,
}: {
  active: ReviewTab;
  onChange: (tab: ReviewTab) => void;
}) {
  return (
    <div role="tablist" aria-label="Achievement status" className="flex flex-wrap gap-2">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={active === tab.id}
          onClick={() => {
            onChange(tab.id);
          }}
          className={`rounded-full px-4 py-1.5 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 ${
            active === tab.id
              ? "bg-violet-600 text-white shadow-md shadow-violet-200"
              : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
