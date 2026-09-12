function Blip({ className, label }: { className: string; label: string }) {
  return (
    <span className={`absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-1.5 ${className}`}>
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-violet-400 opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 ring-2 ring-white" />
      </span>
      <span className="rounded-full border border-violet-200 bg-white/90 px-2 py-0.5 text-[10px] font-semibold text-violet-700 shadow-sm shadow-violet-100">
        {label}
      </span>
    </span>
  );
}

function Radar() {
  return (
    <div aria-hidden="true" className="relative mx-auto h-72 w-72 shrink-0 sm:h-80 sm:w-80">
      <div className="absolute inset-0 rounded-full border border-violet-200 bg-gradient-to-br from-violet-50/90 via-white/80 to-fuchsia-50/90 shadow-xl shadow-violet-200/50 backdrop-blur" />
      <div className="absolute inset-7 rounded-full border border-violet-200/70" />
      <div className="absolute inset-14 rounded-full border border-violet-200/50" />
      <div className="absolute inset-20 rounded-full border border-violet-200/40" />
      <div className="absolute left-1/2 top-2 bottom-2 w-px bg-violet-200/40" />
      <div className="absolute left-2 right-2 top-1/2 h-px bg-violet-200/40" />
      <div className="radar-sweep absolute inset-0 rounded-full bg-[conic-gradient(from_0deg,transparent_0deg,rgba(139,92,246,0.30)_46deg,transparent_85deg)]" />

      <span className="absolute left-1/2 top-1/2 flex h-14 w-14 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-500 text-white shadow-lg shadow-violet-400">
        <span className="ai-ring absolute inset-0 rounded-full border-2 border-violet-400" />
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-6 w-6">
          <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5zM15.5 13l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
        </svg>
      </span>

      <Blip className="left-[16%] top-[30%]" label="Adzuna" />
      <Blip className="left-[80%] top-[22%]" label="LinkedIn" />
      <Blip className="left-[30%] top-[80%]" label="Vector DB" />
    </div>
  );
}

const WHY_LINES = [
  "6 of 7 must-have skills match your profile",
  "Kotlin + fintech experience aligned to the team",
  "Official Adzuna posting — verified and open",
] as const;

export function AiSearchShowcase() {
  return (
    <div className="mx-auto mt-16 w-full max-w-4xl px-6">
      <div className="relative grid gap-8 rounded-[2rem] border border-violet-100 bg-white/85 p-6 shadow-2xl shadow-violet-200/50 backdrop-blur sm:p-8 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-center lg:gap-10">
        <div className="absolute inset-x-16 -top-8 h-24 rounded-[2rem] bg-gradient-to-r from-violet-300/50 via-fuchsia-300/40 to-purple-300/50 blur-3xl" />

        <div className="hidden lg:block">
          <Radar />
        </div>

        <div className="relative">
          <p className="inline-flex items-center gap-2 rounded-full bg-violet-100 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-violet-700">
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3 w-3">
              <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5z" />
            </svg>
            Live AI scan
          </p>

          <div className="mt-3 flex items-center gap-3 rounded-2xl border border-violet-100 bg-gradient-to-r from-violet-50/80 to-fuchsia-50/60 p-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 text-sm font-bold text-white">
              N
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-gray-900">Senior Android Developer</p>
              <p className="truncate text-xs text-gray-500">Nova Labs · Remote</p>
            </div>
            <span className="bg-gradient-to-r from-violet-600 to-fuchsia-600 bg-clip-text text-lg font-bold text-transparent">
              94%
            </span>
          </div>

          <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Why this fits — written by AI for you
          </p>
          <ul className="mt-2 flex flex-col gap-2">
            {WHY_LINES.map((line) => (
              <li
                key={line}
                className="why-reveal flex items-start gap-2 text-sm text-gray-700 opacity-0"
              >
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white">
                  <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-2.5 w-2.5">
                    <path
                      fillRule="evenodd"
                      d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.8 3.8 6.8-6.8a1 1 0 011.4 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
                {line}
              </li>
            ))}
          </ul>

          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-[10px] font-bold text-violet-700">
              Role fit
            </span>
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700">
              Company fit
            </span>
            <span className="rounded-full border border-fuchsia-200 bg-fuchsia-50 px-2.5 py-1 text-[10px] font-bold text-fuchsia-700">
              Vector similarity 0.9
            </span>
          </div>
        </div>

        <div
          aria-hidden="true"
          className="hero-float absolute -top-5 right-6 hidden rounded-2xl border border-violet-100 bg-white/95 px-3.5 py-2.5 shadow-xl shadow-violet-200/60 backdrop-blur lg:block"
        >
          <p className="text-sm font-bold text-gray-900">128 postings</p>
          <p className="text-[10px] font-medium text-gray-500">scanned from 3 sources</p>
        </div>
        <div
          aria-hidden="true"
          className="hero-float-slow absolute -bottom-5 left-6 hidden rounded-2xl border border-violet-100 bg-white/95 px-3.5 py-2.5 shadow-xl shadow-violet-200/60 backdrop-blur lg:block"
        >
          <p className="text-sm font-bold text-gray-900">Profile approved ✓</p>
          <p className="text-[10px] font-medium text-gray-500">you control every field</p>
        </div>
      </div>
    </div>
  );
}
