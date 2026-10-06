"use client";

import { Button } from "@/components/ui/button";
import type { AtsScoreResponse } from "@/lib/api";

function HeroRing({ score }: { score: number }) {
  const angle = Math.round((Math.min(100, Math.max(0, score)) / 100) * 360);
  const ringColor = angle >= 216 ? "#34d399" : angle >= 144 ? "#fbbf24" : "#f87171";
  return (
    <div
      className="relative h-40 w-40 shrink-0 rounded-full"
      style={{
        background: `conic-gradient(${ringColor} ${angle}deg, rgba(255,255,255,0.25) ${angle}deg)`,
      }}
      role="img"
      aria-label={`Overall ATS score ${score} out of 100`}
    >
      <div className="absolute inset-2.5 flex flex-col items-center justify-center rounded-full bg-white shadow-lg">
        <span className="text-4xl font-extrabold tracking-tight text-gray-900">{score}</span>
        <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
          out of 100
        </span>
      </div>
    </div>
  );
}

export function AtsReportHero({
  report,
  onReset,
}: {
  report: AtsScoreResponse;
  onReset: () => void;
}) {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-violet-200/60 bg-white p-8 shadow-xl shadow-violet-100">
      <div aria-hidden="true" className="absolute inset-0 pointer-events-none">
        <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-violet-100 blur-3xl" />
        <div className="absolute -bottom-24 -left-16 h-56 w-56 rounded-full bg-fuchsia-100 blur-3xl" />
      </div>

      <div className="relative flex flex-col gap-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-2">
            <span className="w-fit rounded-full bg-violet-100 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-violet-700">
              ATS report
            </span>
            <h2 className="max-w-2xl text-2xl font-extrabold tracking-tight text-gray-900">
              {report.verdict}
            </h2>
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={onReset}
            className="shrink-0 rounded-xl px-5 py-2.5 text-sm font-semibold"
          >
            Score another job description
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-8">
          <HeroRing score={report.overall_score} />
          <div className="flex min-w-72 flex-1 flex-col gap-4">
            <p className="max-w-prose text-[15px] leading-relaxed text-gray-700">
              {report.summary}
            </p>
            <dl className="grid grid-cols-3 gap-3 text-center">
              {[
                { label: "Matched", value: report.matched_keywords.length, tone: "bg-emerald-50 text-emerald-700" },
                { label: "Missing", value: report.missing_keywords.length, tone: "bg-red-50 text-red-700" },
                { label: "Fixes", value: report.suggestions.length, tone: "bg-violet-50 text-violet-700" },
              ].map((stat) => (
                <div key={stat.label} className={`rounded-xl px-4 py-3 ${stat.tone}`}>
                  <dd className="text-xl font-extrabold">{stat.value}</dd>
                  <dt className="text-xs font-semibold uppercase tracking-wide opacity-80">
                    {stat.label}
                  </dt>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </div>
    </section>
  );
}
