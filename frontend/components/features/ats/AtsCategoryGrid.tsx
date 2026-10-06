"use client";

import type { AtsCategoryScore } from "@/lib/api";
import { scoreTone } from "@/components/features/ats/AtsReportShared";

function CategoryRing({ score }: { score: number }) {
  const angle = Math.round((Math.min(100, Math.max(0, score)) / 100) * 270);
  const tone = scoreTone(score);
  const color = angle >= 216 ? "#10b981" : angle >= 144 ? "#f59e0b" : "#ef4444";
  return (
    <div
      className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-full"
      role="img"
      aria-label={`${score} out of 100`}
      style={{
        background: `conic-gradient(from 135deg, ${color} ${angle}deg, #ede9fe ${angle}deg)`,
      }}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white">
        <span className={`text-sm font-bold ${tone.text}`}>{Math.round(score)}</span>
      </div>
    </div>
  );
}

export function AtsCategoryGrid({ categories }: { categories: AtsCategoryScore[] }) {
  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-sm font-bold text-gray-900">Category breakdown</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        {categories.map((category) => (
          <article
            key={category.name}
            className="flex flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex items-center gap-4">
              <CategoryRing score={category.score} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-gray-900">{category.name}</p>
                <p className="text-xs font-medium text-gray-500">
                  {Math.round(category.weight * 100)}% of your score
                </p>
              </div>
            </div>
            <p className="text-sm leading-relaxed text-gray-600">{category.analysis}</p>
            {category.issues.length > 0 && (
              <ul className="flex flex-col gap-1.5 border-t border-gray-100 pt-3">
                {category.issues.map((issue) => (
                  <li key={issue} className="flex items-start gap-2 text-xs text-gray-500">
                    <span aria-hidden className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-gray-400" />
                    {issue}
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
