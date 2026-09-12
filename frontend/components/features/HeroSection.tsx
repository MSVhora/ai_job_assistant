import Link from "next/link";

import { AiSearchShowcase } from "@/components/features/AiSearchShowcase";

function SparkleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5zM15.5 13l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4 text-violet-600">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.7-9.3a1 1 0 00-1.4-1.4L9 10.6 7.7 9.3a1 1 0 00-1.4 1.4l2 2a1 1 0 001.4 0l4-4z"
        clipRule="evenodd"
      />
    </svg>
  );
}

const STATS = [
  "Multi-source job discovery",
  "Human-reviewed profiles",
  "Explainable AI matches",
] as const;

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pb-24 pt-16 text-gray-900">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-24 top-4 h-80 w-80 rounded-full bg-violet-300/60 blur-3xl" />
        <div className="absolute -right-20 top-20 h-80 w-80 rounded-full bg-fuchsia-300/50 blur-3xl" />
        <div className="absolute left-1/3 top-80 h-64 w-64 rounded-full bg-purple-200/60 blur-3xl" />
        <svg
          className="absolute left-16 top-40 h-8 w-8 text-violet-400/70"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path d="M4 16c3-8 6 4 9-4s4 6 7-2" />
        </svg>
        <svg
          className="absolute right-24 top-56 h-6 w-6 text-fuchsia-400/70"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <circle cx="12" cy="12" r="6" />
          <circle cx="12" cy="12" r="1.5" fill="currentColor" />
        </svg>
      </div>

      <div className="mx-auto flex max-w-4xl flex-col items-center gap-6 px-6 text-center">
        <p className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-wide text-violet-700 shadow-sm shadow-violet-100">
          <SparkleIcon className="h-3.5 w-3.5" />
          AI-Powered Job Matching
        </p>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-6xl sm:leading-[1.1]">
          Unlock Your Future:{" "}
          <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
            Find Your Perfect Job
          </span>{" "}
          Today!
        </h1>
        <p className="max-w-2xl text-base leading-relaxed text-gray-600 sm:text-lg">
          Upload your resume once — AI drafts your profile, you review every field, and matches
          from all your job sources arrive ranked with plain-language explanations of why each
          role fits.
        </p>
        <div className="flex flex-col items-center gap-3 sm:flex-row">
          <Link
            href="/get-started"
            className="rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-violet-500/40 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-violet-500/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Start Finding Your Next Job
          </Link>
        </div>
        <ul className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-gray-600">
          {STATS.map((stat) => (
            <li key={stat} className="flex items-center gap-1.5">
              <CheckIcon />
              {stat}
            </li>
          ))}
        </ul>
      </div>

      <AiSearchShowcase />
    </section>
  );
}
