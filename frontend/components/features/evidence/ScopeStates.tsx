"use client";

export function ScopeStates({
  configured,
  pending,
  failed,
  empty,
  neverRefreshed,
  onRetry,
}: {
  configured: boolean;
  pending: boolean;
  failed: boolean;
  empty: boolean;
  neverRefreshed: boolean;
  onRetry: () => void;
}) {
  if (!configured) {
    return <p className="text-sm text-gray-600">Connect GitHub to list your repositories.</p>;
  }
  if (pending) {
    return <div className="h-24 animate-pulse rounded-2xl bg-gray-100" aria-busy="true" />;
  }
  if (failed) {
    return (
      <div role="alert" className="flex items-center justify-between gap-3 text-sm text-red-700">
        <span>Could not load your repositories. Check that the API is running and try again.</span>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-full border border-red-300 px-3 py-1 text-xs font-semibold hover:bg-red-50"
        >
          Retry
        </button>
      </div>
    );
  }
  if (empty) {
    return (
      <p className="text-sm text-gray-600">
        {neverRefreshed
          ? "No repositories loaded yet — press Refresh from GitHub."
          : "No repositories found for this token."}
      </p>
    );
  }
  return null;
}
