import Link from "next/link";

import { Reveal } from "@/components/features/Reveal";

function UploadIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-6 w-6"
    >
      <path d="M12 16V4m0 0l-4 4m4-4l4 4" />
      <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="h-6 w-6">
      <path d="M12 2l2.2 5.8L20 10l-5.8 2.2L12 18l-2.2-5.8L4 10l5.8-2.2L12 2zM18.5 15l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
    </svg>
  );
}

function ReviewIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-6 w-6"
    >
      <path d="M9 12l2 2 4-4" />
      <circle cx="12" cy="12" r="9" />
    </svg>
  );
}

function MatchIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-6 w-6"
    >
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </svg>
  );
}

const STEPS = [
  {
    title: "Upload your resume",
    description: "Drop in a PDF or DOCX — parsed in seconds, nothing shared.",
    Icon: UploadIcon,
    ai: false,
  },
  {
    title: "AI drafts your profile",
    description: "Skills, seniority, preferences and more, extracted automatically.",
    Icon: SparkIcon,
    ai: true,
  },
  {
    title: "You review & approve",
    description: "Every field is editable. Corrections feed the audit trail.",
    Icon: ReviewIcon,
    ai: false,
  },
  {
    title: "Matches roll in",
    description: "Ranked openings with a plain-language why for each role.",
    Icon: MatchIcon,
    ai: true,
  },
] as const;

function FlowArrow() {
  return (
    <div
      className="flex h-16 w-16 shrink-0 items-center justify-center self-center lg:h-12 lg:w-24"
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 96 44"
        className="h-11 w-24 max-lg:rotate-90"
        fill="none"
      >
        <defs>
          <linearGradient id="flow-gradient" x1="0" y1="0" x2="96" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#8b5cf6" />
            <stop offset="1" stopColor="#d946ef" />
          </linearGradient>
        </defs>
        <path
          id="flow-path"
          d="M4 30 C 24 30, 30 12, 48 12 S 72 22, 84 22"
          stroke="url(#flow-gradient)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray="7 7"
          className="flow-dash"
        />
        <path
          d="M78 16 L86 22 L78 28"
          stroke="url(#flow-gradient)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle r="3.5" fill="#8b5cf6" className="drop-shadow-[0_0_6px_rgba(139,92,246,0.8)]">
          <animateMotion dur="2.2s" repeatCount="indefinite" rotate="auto">
            <mpath href="#flow-path" />
          </animateMotion>
        </circle>
      </svg>
    </div>
  );
}

export function HowItWorksSection() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-transparent via-violet-100/40 to-transparent py-20 text-gray-900">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/4 top-16 h-72 w-72 rounded-full bg-violet-300/30 blur-3xl" />
        <div className="absolute right-1/4 top-40 h-72 w-72 rounded-full bg-fuchsia-300/25 blur-3xl" />
      </div>
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="flex flex-col items-center gap-4 text-center">
          <p className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-wide text-violet-700 shadow-sm shadow-violet-100">
            How it works
          </p>
          <h2 className="max-w-3xl text-3xl font-bold tracking-tight sm:text-5xl">
            From resume to role in{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              four steps
            </span>
          </h2>
          <p className="max-w-2xl text-base text-gray-600 sm:text-lg">
            A guided pipeline with you in control at every step — AI does the heavy lifting,
            you make the calls.
          </p>
        </Reveal>

        <div className="relative mt-14 flex flex-col items-stretch gap-2 lg:flex-row lg:items-stretch lg:gap-0">
          {STEPS.map((step, i) => (
            <div key={step.title} className="contents">
              <Reveal className="flex-1 [&>*]:h-full">
                <div className="group relative h-full rounded-3xl border border-violet-200/70 bg-gradient-to-br from-white via-violet-50/70 to-fuchsia-50/50 p-6 text-center shadow-xl shadow-violet-200/50 transition-all hover:-translate-y-1 hover:shadow-2xl hover:shadow-violet-300/60">
                  <span className="absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-500 text-[11px] font-bold text-white shadow-sm shadow-violet-300">
                    {i + 1}
                  </span>
                  <span className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-lg shadow-violet-300 transition-transform group-hover:scale-110">
                    <span
                      aria-hidden="true"
                      className="ai-ring absolute inset-0 rounded-2xl border-2 border-violet-400"
                    />
                    <step.Icon />
                  </span>
                  <h3 className="mt-4 text-lg font-bold">{step.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-gray-600">
                    {step.description}
                  </p>
                  {step.ai === true && (
                    <p className="mt-3 inline-flex items-center gap-1 rounded-full bg-violet-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-violet-700">
                      <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3" aria-hidden="true">
                        <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5z" />
                      </svg>
                      AI step
                    </p>
                  )}
                </div>
              </Reveal>
              {i < STEPS.length - 1 && <FlowArrow />}
            </div>
          ))}
        </div>

        <Reveal className="mt-12 flex justify-center">
          <Link
            href="/get-started"
            className="rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-10 py-4 text-base font-semibold text-white shadow-xl shadow-violet-500/40 transition hover:-translate-y-0.5 hover:shadow-2xl hover:shadow-violet-500/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Start Finding Your Next Job
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
