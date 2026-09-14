import type { InputHTMLAttributes } from "react";

export function Checkbox({
  label,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label
      className={`flex cursor-pointer items-center gap-2 text-sm text-gray-700 ${className ?? ""}`}
    >
      <input
        type="checkbox"
        className="h-4 w-4 rounded border-gray-300 text-violet-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 aria-[invalid=true]:border-red-400"
        {...props}
      />
      {label}
    </label>
  );
}
