"use client";

import { useEffect, useState } from "react";

const STAGES = [
  { label: "Reading resume", end: 30 },
  { label: "Analysing the job", end: 55 },
  { label: "AI scoring", end: 85 },
  { label: "Building report", end: 100 },
] as const;

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3.5 w-3.5">
      <path
        fillRule="evenodd"
        d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.8 3.8 6.8-6.8a1 1 0 011.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function AtsLoadingView() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setProgress((current) => Math.min(current + 1, 95));
    }, 350);
    return () => clearInterval(timer);
  }, []);

  const stageIndex = STAGES.findIndex((stage) => progress < stage.end);
  const currentStage = STAGES[stageIndex === -1 ? STAGES.length - 1 : stageIndex];

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center gap-5 rounded-2xl border border-violet-100 bg-white p-8 shadow-sm"
    >
      <div
        className="flex h-14 w-14 items-center justify-center rounded-full border-4 border-violet-100 border-t-violet-600 motion-safe:animate-spin"
        aria-hidden="true"
      />
      <p className="text-sm font-semibold text-gray-900">{currentStage.label}…</p>
      <div className="h-2.5 w-64 overflow-hidden rounded-full bg-violet-100 sm:w-80" role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="ATS scoring progress"
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
      <ol className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs">
        {STAGES.map((stage, index) => {
          const done = progress >= stage.end;
          const active = index === stageIndex;
          return (
            <li
              key={stage.label}
              className={`flex items-center gap-1 ${
                done ? "text-emerald-600" : active ? "font-semibold text-violet-700" : "text-gray-400"
              }`}
            >
              {done ? <CheckIcon /> : <span aria-hidden>{index + 1}.</span>}
              {stage.label}
            </li>
          );
        })}
      </ol>
      <p className="text-center text-xs text-gray-500">
        AI is comparing your resume against the job description — usually 10–30 seconds.
      </p>
    </div>
  );
}
