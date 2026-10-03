import Link from "next/link";

export function NoProfileState() {
  return (
    <section
      aria-labelledby="matches-heading"
      className="rounded-3xl border border-dashed border-violet-200 bg-white/70 p-8 text-center shadow-lg shadow-gray-100"
    >
      <h2 id="matches-heading" className="text-lg font-bold tracking-tight text-gray-900">
        Ranked matches
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-gray-600">
        Matches rank stored postings against a profile.{" "}
        <Link
          href="/profile"
          className="font-semibold text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Create a profile
        </Link>{" "}
        or run a search — matches appear here after the run finishes.
      </p>
    </section>
  );
}

export function MatchesPending() {
  return (
    <div
      className="h-96 animate-pulse rounded-3xl border border-gray-200 bg-white/60"
      aria-busy="true"
      aria-live="polite"
    />
  );
}

export function MatchesError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section
      aria-labelledby="matches-heading"
      className="rounded-3xl border border-gray-200 bg-white p-6 shadow-lg shadow-gray-100"
    >
      <h2 id="matches-heading" className="text-lg font-bold tracking-tight text-gray-900">
        Ranked matches
      </h2>
      <p role="alert" className="mt-3 text-sm text-red-700">
        Could not load matches: {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
      >
        Retry
      </button>
    </section>
  );
}
