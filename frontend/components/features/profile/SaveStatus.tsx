"use client";

export function SaveStatus({
  isSaving,
  error,
  savedRevisionSource,
}: {
  isSaving: boolean;
  error: string | null;
  savedRevisionSource: string | null;
}) {
  return (
    <div aria-live="polite" aria-atomic="true" className="text-sm">
      {isSaving && <p className="text-gray-600">Saving…</p>}
      {!isSaving && error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}
      {!isSaving && !error && savedRevisionSource && (
        <p className="text-emerald-700">Saved — revision recorded ({savedRevisionSource})</p>
      )}
    </div>
  );
}
