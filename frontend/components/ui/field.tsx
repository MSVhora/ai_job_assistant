import type { ReactNode } from "react";

export function Field({
  label,
  htmlFor,
  error,
  hint,
  badge,
  children,
}: {
  label: string;
  htmlFor?: string;
  error?: string;
  hint?: string;
  badge?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={htmlFor} className="text-sm font-medium text-gray-800 dark:text-gray-200">
          {label}
        </label>
        {badge}
      </div>
      {children}
      {hint && !error && <p className="text-xs text-gray-500 dark:text-gray-400">{hint}</p>}
      {error && (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
