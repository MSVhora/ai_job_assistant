import Link from "next/link";

function SparkleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5zM15.5 13l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
    </svg>
  );
}

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

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <path d="M12 16V4m0 0l-4 4m4-4l4 4" />
      <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
    </svg>
  );
}

function ProfileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
    </svg>
  );
}

function KeyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <circle cx="8" cy="14" r="4" />
      <path d="M11 11l9-9m-3 3l3 3" />
    </svg>
  );
}

function JobsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2M3 12h18" />
    </svg>
  );
}

function AtsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </svg>
  );
}

function BuilderIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" />
    </svg>
  );
}

function JobSearchPreview() {
  return (
    <div className="mt-5 flex flex-col gap-2 rounded-2xl border border-gray-100 bg-gray-50/80 p-3">
      <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-2.5 shadow-sm">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-[10px] font-bold text-blue-700">IBM</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-semibold text-gray-900">Software Engineer, IBM</span>
          <span className="block text-[11px] text-gray-500">Engineering</span>
        </span>
        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700">Great fit</span>
      </div>
      <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-2.5 shadow-sm">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-[10px] font-bold text-emerald-700">MS</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-semibold text-gray-900">HR Manager, Microsoft</span>
          <span className="block text-[11px] text-gray-500">Operations</span>
        </span>
        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">Applied</span>
      </div>
    </div>
  );
}

function UploadPreview() {
  return (
    <div className="mt-5 flex flex-col gap-2 rounded-2xl border border-gray-100 bg-gray-50/80 p-3">
      <div className="flex items-center gap-3 rounded-xl border border-dashed border-violet-300 bg-violet-50/60 p-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
          <UploadIcon />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-semibold text-gray-900">
            resume_2026.pdf
          </span>
          <span className="block text-[11px] text-gray-500">Drop or browse to upload</span>
        </span>
      </div>
      <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-2.5 shadow-sm">
        <span className="h-8 w-8 shrink-0 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-400" />
        <span className="min-w-0 flex-1 space-y-1.5">
          <span className="block h-2 w-24 rounded-full bg-gray-200" />
          <span className="block h-2 w-16 rounded-full bg-gray-100" />
        </span>
        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700">
          AI drafting…
        </span>
      </div>
    </div>
  );
}

function ProfilePreview() {
  return (
    <div className="mt-5 rounded-2xl border border-gray-100 bg-gray-50/80 p-3">
      <div className="rounded-xl border border-gray-100 bg-white p-3 shadow-sm">
        <div className="flex items-center gap-2.5">
          <span className="h-8 w-8 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-400" />
          <span className="flex-1">
            <span className="block h-2 w-20 rounded-full bg-gray-300" />
            <span className="mt-1.5 block h-2 w-14 rounded-full bg-gray-200" />
          </span>
          <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700">Reviewed</span>
        </div>
        <div className="mt-3 space-y-1.5">
          <span className="block h-2 w-full rounded-full bg-gray-100" />
          <span className="block h-2 w-5/6 rounded-full bg-gray-100" />
          <span className="block h-2 w-2/3 rounded-full bg-gray-100" />
        </div>
      </div>
    </div>
  );
}

function SetupPreview() {
  return (
    <div className="mt-5 flex flex-col gap-2 rounded-2xl border border-gray-100 bg-gray-50/80 p-3">
      {["Gemini", "Adzuna", "Apify"].map((name) => (
        <div key={name} className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-2.5 shadow-sm">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
            <KeyIcon />
          </span>
          <span className="flex-1 text-xs font-semibold text-gray-900">{name} key</span>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">Active</span>
        </div>
      ))}
    </div>
  );
}

function BarsPreview() {
  return (
    <div className="mt-5 rounded-2xl border border-gray-100 bg-white/60 p-3">
      <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
        <div className="flex items-center gap-2.5">
          <span className="h-8 w-8 rounded-lg bg-gray-200" />
          <span className="flex-1 space-y-1.5">
            <span className="block h-2 w-24 rounded-full bg-gray-200" />
            <span className="block h-2 w-16 rounded-full bg-gray-200/70" />
          </span>
        </div>
        <div className="mt-3 space-y-1.5">
          <span className="block h-2 w-full rounded-full bg-gray-200/70" />
          <span className="block h-2 w-4/5 rounded-full bg-gray-200/70" />
        </div>
      </div>
    </div>
  );
}

type GetStartedOption = {
  eyebrow: string;
  title: string;
  description: string;
  Icon: () => React.ReactElement;
  Preview: () => React.ReactElement;
  href?: string;
  popular?: boolean;
  disabled?: boolean;
};

const OPTIONS: GetStartedOption[] = [
  {
    eyebrow: "AI JOB SEARCH",
    title: "Create profile",
    description: "Upload a resume and let AI draft your profile for targeted matching.",
    Icon: UploadIcon,
    Preview: UploadPreview,
    href: "/upload",
    popular: false,
  },
  {
    eyebrow: "AI JOB PROFILES",
    title: "Manage profiles",
    description: "Review, edit and manage profile tracks for targeted matching.",
    Icon: ProfileIcon,
    Preview: ProfilePreview,
    href: "/profile",
    popular: false,
  },
  {
    eyebrow: "JOB OPENINGS",
    title: "Job openings",
    description: "Browse ranked openings from every enabled source and act on your matches.",
    Icon: JobsIcon,
    Preview: JobSearchPreview,
    href: "/jobs",
    popular: true,
  },
  {
    eyebrow: "AI ATS SCORE",
    title: "Score & fix your resume",
    description: "Score your resume against applicant tracking systems and get fixes.",
    Icon: AtsIcon,
    Preview: BarsPreview,
    disabled: true,
  },
  {
    eyebrow: "AI RESUME BUILDER",
    title: "Build tailored resumes",
    description: "Generate tailored, ATS-ready resumes for every application.",
    Icon: BuilderIcon,
    Preview: BarsPreview,
    disabled: true,
  },
  {
    eyebrow: "API SETUP",
    title: "Add your API keys",
    description: "Add Gemini, Adzuna and Apify keys to power AI features and sources.",
    Icon: KeyIcon,
    Preview: SetupPreview,
    href: "/setup",
    popular: false,
  },
];

export const metadata = {
  title: "Get started",
  description: "Choose where to start: job search, profiles, API keys and more.",
};

export default function GetStartedPage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-transparent" />
        <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-violet-300/40 blur-3xl" />
        <div className="absolute -right-24 top-32 h-72 w-72 rounded-full bg-fuchsia-300/30 blur-3xl" />
      </div>

      <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-3 px-6 pb-16 pt-16 text-center">
        <p className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-wide text-violet-700 shadow-sm shadow-violet-100">
          <SparkleIcon className="h-3.5 w-3.5" />
          Choose your path
        </p>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          What would you like to do{" "}
          <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
            today?
          </span>
        </h1>
        <p className="max-w-xl text-base text-gray-600 sm:text-lg">
          Pick a starting point — every path keeps you in control while AI does the heavy lifting.
        </p>

        <div className="mt-12 grid w-full gap-6 pt-3 sm:grid-cols-2 lg:grid-cols-3">
          {OPTIONS.map((option) =>
            option.disabled ? (
              <div
                key={option.eyebrow}
                aria-disabled="true"
                className="relative flex flex-col rounded-3xl border border-gray-200 bg-gray-50/80 p-5 text-left"
              >
                <span className="absolute right-4 top-4 rounded-full bg-gray-200 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                  Coming soon
                </span>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                  {option.eyebrow}
                </p>
                <div className="mt-1.5 flex items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gray-200 text-gray-400">
                    <option.Icon />
                  </span>
                  <h2 className="text-base font-bold text-gray-400">{option.title}</h2>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-gray-400">{option.description}</p>
                <option.Preview />
              </div>
            ) : (
              <Link
                key={option.eyebrow}
                href={option.href ?? "/"}
                aria-label={`${option.title} — open ${option.eyebrow.toLowerCase()}`}
                className="group relative flex flex-col rounded-3xl border border-gray-200 bg-white p-5 text-left shadow-lg shadow-gray-100 transition-all hover:-translate-y-1 hover:border-violet-500 hover:shadow-xl hover:shadow-violet-200/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
              >
                {option.popular && (
                  <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-violet-600 px-4 py-1 text-xs font-bold text-white shadow-md shadow-violet-300">
                    Most popular
                  </span>
                )}
                <span
                  aria-hidden="true"
                  className="absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded-full border-2 border-gray-300 text-transparent transition-colors group-hover:border-violet-600 group-hover:bg-violet-600 group-hover:text-white"
                >
                  <CheckIcon />
                </span>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                  {option.eyebrow}
                </p>
                <div className="mt-1.5 flex items-center gap-3 pr-8">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200 transition-transform group-hover:scale-110">
                    <option.Icon />
                  </span>
                  <h2 className="text-base font-bold text-gray-900">{option.title}</h2>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-gray-600">{option.description}</p>
                <option.Preview />
              </Link>
            ),
          )}
        </div>
      </div>
    </main>
  );
}
