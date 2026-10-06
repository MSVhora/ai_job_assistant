import { DuplicateRunError } from "@/lib/api";

export function SearchRunErrors({
  error,
  onSearchStarted,
  onClose,
}: {
  error: Error | null;
  onSearchStarted: (searchId: string) => void;
  onClose: () => void;
}) {
  if (error === null) return null;
  const duplicateRunError = error instanceof DuplicateRunError ? error : null;
  return (
    <>
      {duplicateRunError !== null && (
        <div role="alert" className="flex flex-col gap-2 text-xs text-red-600">
          <span>A search for this profile and source is already running.</span>
          {duplicateRunError.activeSearchId !== null && (
            <button
              type="button"
              className="self-start rounded-lg border border-red-200 px-3 py-1.5 font-semibold text-red-700 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
              onClick={() => {
                const activeId = duplicateRunError.activeSearchId;
                if (activeId !== null) {
                  onSearchStarted(activeId);
                  onClose();
                }
              }}
            >
              Go to active run
            </button>
          )}
        </div>
      )}
      {duplicateRunError === null && (
        <p role="alert" className="text-xs text-red-600">
          {error.message}
        </p>
      )}
    </>
  );
}
