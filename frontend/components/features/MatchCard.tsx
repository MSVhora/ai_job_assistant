export const MATCH_STORIES = [
  {
    role: "Senior Software Engineer",
    company: "Nova Labs",
    initial: "N",
    chips: ["€85k–€105k", "Remote, EU", "Engineering"],
    summary:
      "Own core services of a health platform used by 4M people. Ship features weekly across a 12-person product engineering guild.",
    why: "Your 7 years of Kotlin and TypeScript, Play Store launch experience and offline-first architecture work line up exactly.",
    quals: ["Shipped 3 top-100 apps", "Led modularization of a 200k-LOC monolith", "CI/CD for mobile at scale"],
    score: 94,
    bar: "w-[94%]",
    label: "Perfect fit",
  },
  {
    role: "Lead Product Manager",
    company: "Arcadia",
    initial: "A",
    chips: ["$130k–$160k", "Hybrid, New York", "Product"],
    summary:
      "Drive the roadmap for a B2B analytics suite. Own discovery, prioritization and launch across two squads.",
    why: "Your PLG background and track record of 0→1 launches match the growth-stage roadmap perfectly.",
    quals: ["Launched 2 products past $5M ARR", "Led squads of 8+ engineers", "Strong SQL + experimentation"],
    score: 92,
    bar: "w-[92%]",
    label: "Perfect fit",
  },
  {
    role: "Engineering Manager",
    company: "Brightpath",
    initial: "B",
    chips: ["£95k–£120k", "Hybrid, London", "Engineering"],
    summary:
      "Lead two platform teams building payments infrastructure. Own delivery, hiring and architectural direction.",
    why: "Your mix of hands-on backend depth and 3 years managing two teams mirrors this role's mandate.",
    quals: ["Grew team from 5 to 14", "Cut incident rate 40%", "Still reviews critical RFCs"],
    score: 90,
    bar: "w-[90%]",
    label: "Strong fit",
  },
  {
    role: "Senior Project Manager",
    company: "Orbita",
    initial: "O",
    chips: ["€75k–€95k", "Remote, EU", "Program"],
    summary:
      "Coordinate a multi-vendor cloud migration across 6 squads. Own timelines, risks and stakeholder reporting.",
    why: "Your PMP + agile background and migration experience de-risk their biggest initiative this year.",
    quals: ["Delivered €10M+ programs", "PMP and SAFe certified", "Ran 40-vendor vendor map"],
    score: 89,
    bar: "w-[89%]",
    label: "Strong fit",
  },
  {
    role: "Business Analyst",
    company: "Datawave",
    initial: "D",
    chips: ["$90k–$110k", "Hybrid, Chicago", "Analytics"],
    summary:
      "Turn operational data into decisions: requirements, dashboards and process models for the logistics arm.",
    why: "Your SQL depth, Tableau dashboards and logistics domain knowledge cover every line of their brief.",
    quals: ["Built 30+ exec dashboards", "Six Sigma Green Belt", "Automated weekly reporting suite"],
    score: 87,
    bar: "w-[87%]",
    label: "Strong fit",
  },
] as const;

function SparkleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5zM15.5 13l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-3.5 w-3.5 shrink-0 text-emerald-500"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M16.7 5.3a1 1 0 010 1.4l-8 8a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.4L8 12.6l7.3-7.3a1 1 0 011.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function MatchCard({ story }: { story: (typeof MATCH_STORIES)[number] }) {
  return (
    <article className="h-full rounded-3xl bg-gradient-to-br from-violet-600 via-purple-600 to-fuchsia-500 p-px shadow-2xl shadow-violet-300/50">
      <div className="relative flex h-full flex-col gap-5 overflow-hidden rounded-[calc(1.5rem-1px)] bg-white p-6 sm:flex-row sm:gap-6 sm:p-7">
        <SparkleIcon className="pointer-events-none absolute -right-3 -top-3 h-20 w-20 text-violet-100" />
        <SparkleIcon className="pointer-events-none absolute -bottom-4 left-1/3 h-14 w-14 text-fuchsia-100/80" />

        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-3">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-base font-bold text-white ring-4 ring-violet-100">
              {story.initial}
            </span>
            <div className="min-w-0">
              <h3 className="truncate text-lg font-bold text-gray-900">{story.role}</h3>
              <p className="text-sm font-medium text-gray-500">{story.company}</p>
            </div>
            <span className="ml-auto inline-flex shrink-0 items-center gap-1 rounded-full bg-violet-600 px-2.5 py-1 text-[10px] font-bold text-white shadow-md shadow-violet-300">
              <SparkleIcon className="h-3 w-3" />
              AI MATCH
            </span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {story.chips.map((chip) => (
              <span
                key={chip}
                className="rounded-full border border-violet-100 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700"
              >
                {chip}
              </span>
            ))}
          </div>
          <div className="mt-4 rounded-2xl border border-violet-100 bg-violet-50/50 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-violet-500">
              Summary
            </p>
            <p className="mt-1.5 text-sm leading-relaxed text-gray-600">{story.summary}</p>
          </div>
        </div>

        <div className="min-w-0 flex-1 rounded-2xl bg-gradient-to-br from-violet-50 via-white to-fuchsia-50 p-4 ring-1 ring-violet-100">
          <p className="flex items-center gap-1.5 text-sm font-bold text-gray-900">
            <SparkleIcon className="h-4 w-4 text-violet-600" />
            Why this is a good fit
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-gray-600">{story.why}</p>
          <p className="mt-3 text-sm font-bold text-gray-900">Qualifications</p>
          <ul className="mt-1.5 space-y-1.5">
            {story.quals.map((qual) => (
              <li key={qual} className="flex items-start gap-1.5 text-sm text-gray-600">
                <CheckIcon />
                {qual}
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs font-semibold text-gray-600">
              <span>Match score</span>
              <span className="font-bold text-violet-700">{story.score}/100</span>
            </div>
            <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-violet-100">
              <div
                className={`h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 ${story.bar}`}
              />
            </div>
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">
              <CheckIcon />
              {story.label}
            </p>
          </div>
        </div>
      </div>
    </article>
  );
}
