import Link from "next/link";

function SparkleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5zM15.5 13l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
    </svg>
  );
}

export function SiteFooter() {
  return (
    <footer className="relative overflow-hidden border-t border-violet-100 bg-gradient-to-b from-transparent to-violet-100/70 text-gray-900">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 h-px w-2/3 -translate-x-1/2 bg-gradient-to-r from-transparent via-violet-400 to-transparent" />
        <div className="absolute -top-24 left-1/2 h-48 w-[36rem] -translate-x-1/2 rounded-full bg-violet-300/40 blur-3xl" />
        <div className="absolute bottom-0 left-1/4 h-40 w-80 rounded-full bg-fuchsia-300/30 blur-3xl" />
      </div>

      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="flex flex-col items-center gap-4 text-center">
          <Link
            href="/"
            className="flex items-center gap-2.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-fuchsia-500 shadow-md shadow-violet-300">
              <SparkleIcon className="h-5 w-5 text-white" />
            </span>
            <span className="text-lg font-bold tracking-tight">
              Job<span className="text-violet-600">Gen</span>
              <span className="text-fuchsia-500">.</span>
            </span>
          </Link>
          <p className="max-w-md text-sm leading-relaxed text-gray-600">
            Self-hosted, bring-your-own-key AI job search. JobGen drafts your profile, you stay in
            control, and every match comes with a plain-language explanation.
          </p>
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-violet-100 pt-6 sm:flex-row">
          <p className="text-xs font-medium text-gray-500">
            © 2026 JobGen. Self-hosted — your data stays yours.
          </p>
          <div className="flex items-center gap-5">
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-500">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              All systems operational
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
