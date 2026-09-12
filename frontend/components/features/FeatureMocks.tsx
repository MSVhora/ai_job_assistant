function SparkleBadge() {
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-500 shadow-md shadow-violet-300">
      <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5 text-white" aria-hidden="true">
        <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5z" />
      </svg>
    </span>
  );
}

function Line({ width, highlight }: { width: string; highlight?: boolean }) {
  return (
    <div
      className={`h-2 rounded-full ${highlight ? "bg-violet-200" : "bg-gray-100"} ${width}`}
    />
  );
}

export function ResumeBuilderMock() {
  return (
    <div aria-hidden="true" className="relative mx-auto mt-10 w-full max-w-xs pb-8">
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xl shadow-violet-100">
        <p className="text-center text-sm font-bold text-gray-900">Alex Morgan</p>
        <p className="mt-0.5 text-center text-[10px] font-medium text-gray-400">
          Senior Product Designer · Berlin
        </p>
        <div className="mt-4 space-y-2">
          <Line width="w-1/3" highlight />
          <Line width="w-full" />
          <Line width="w-5/6" />
          <Line width="w-full" />
          <Line width="w-2/3" />
          <Line width="w-1/3" highlight />
          <Line width="w-4/5" />
          <Line width="w-3/5" />
        </div>
      </div>
      <div className="absolute -bottom-1 left-1/2 flex w-[90%] -translate-x-1/2 items-center gap-2 rounded-full border-2 border-violet-500 bg-white py-2 pl-4 pr-2 shadow-xl shadow-violet-200">
        <span className="feature-type overflow-hidden whitespace-nowrap text-xs font-medium text-gray-700">
          Make it less wordy
        </span>
        <span className="feature-caret h-3.5 w-px bg-violet-600" />
        <span className="ml-auto">
          <SparkleBadge />
        </span>
      </div>
    </div>
  );
}

export function AtsScoreMock() {
  const r = 34;
  const c = 2 * Math.PI * r;
  const offset = c * 0.08;
  return (
    <div aria-hidden="true" className="mx-auto mt-10 flex w-full max-w-xs flex-col items-center gap-4 pb-2">
      <div className="relative">
        <svg viewBox="0 0 88 88" className="h-28 w-28 -rotate-90">
          <circle cx="44" cy="44" r={r} fill="none" strokeWidth="9" className="stroke-violet-100" />
          <circle
            cx="44"
            cy="44"
            r={r}
            fill="none"
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={offset}
            className="feature-gauge stroke-violet-600"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-gray-900">92</span>
          <span className="text-[9px] font-semibold uppercase tracking-wider text-violet-600">
            ATS Score
          </span>
        </div>
      </div>
      <ul className="w-full space-y-2">
        {[
          { label: "Keywords match job description", ok: true },
          { label: "Clear section headings", ok: true },
          { label: "Add 2 more measurable results", ok: false },
        ].map((item) => (
          <li
            key={item.label}
            className="flex items-center gap-2 rounded-lg border border-gray-100 bg-white px-3 py-2 text-xs font-medium text-gray-600 shadow-sm"
          >
            <span
              className={`flex h-4 w-4 items-center justify-center rounded-full ${
                item.ok ? "bg-violet-600" : "bg-amber-400"
              }`}
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3 text-white">
                {item.ok ? (
                  <path
                    fillRule="evenodd"
                    d="M16.7 5.3a1 1 0 010 1.4l-8 8a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.4L8 12.6l7.3-7.3a1 1 0 011.4 0z"
                    clipRule="evenodd"
                  />
                ) : (
                  <path d="M6 10h8v1.5H6z" />
                )}
              </svg>
            </span>
            {item.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ProfileMock() {
  const rows = [
    { field: "Seniority", value: "Senior (7+ yrs)" },
    { field: "Location", value: "Berlin · Remote OK" },
    { field: "Work auth", value: "EU citizen" },
    { field: "Salary band", value: "€75k – €95k" },
  ];
  return (
    <div aria-hidden="true" className="mx-auto mt-10 w-full max-w-xs pb-2">
      <div className="flex items-center gap-2 rounded-t-2xl border border-b-0 border-violet-100 bg-violet-50/70 px-4 py-2.5">
        <SparkleBadge />
        <p className="text-xs font-semibold text-violet-700">AI drafting your profile…</p>
      </div>
      <ul className="space-y-2 rounded-b-2xl border border-violet-100 bg-white p-4 shadow-xl shadow-violet-100">
        {rows.map((row, i) => (
          <li
            key={row.field}
            className={`feature-row flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 ${`feature-d${i + 1}`}`}
          >
            <span className="text-xs font-medium text-gray-500">{row.field}</span>
            <span className="flex items-center gap-1.5 text-xs font-semibold text-gray-900">
              {row.value}
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5 text-violet-600">
                <path
                  fillRule="evenodd"
                  d="M16.7 5.3a1 1 0 010 1.4l-8 8a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.4L8 12.6l7.3-7.3a1 1 0 011.4 0z"
                  clipRule="evenodd"
                />
              </svg>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MatchesMock() {
  const matches = [
    { title: "Senior Android Developer", company: "Nova Labs", score: "94%", width: "w-[94%]" },
    { title: "Mobile Engineer, Fintech", company: "Northwind", score: "88%", width: "w-[88%]" },
  ];
  return (
    <div aria-hidden="true" className="mx-auto mt-10 w-full max-w-xs pb-2">
      <div className="mb-3 flex justify-center">
        <span className="feature-pulse inline-flex items-center gap-1.5 rounded-full bg-violet-600 px-3 py-1 text-[10px] font-semibold text-white shadow-lg shadow-violet-300">
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3">
            <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5z" />
          </svg>
          Ranked in 2m 14s
        </span>
      </div>
      <ul className="space-y-2.5">
        {matches.map((match) => (
          <li
            key={match.title}
            className="rounded-xl border border-gray-100 bg-white p-3 shadow-xl shadow-violet-100"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-xs font-semibold text-gray-900">{match.title}</p>
              <span className="shrink-0 text-xs font-bold text-violet-700">{match.score}</span>
            </div>
            <p className="mt-0.5 text-[10px] font-medium text-gray-400">{match.company}</p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-violet-50">
              <div
                className={`feature-bar h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 ${match.width}`}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
