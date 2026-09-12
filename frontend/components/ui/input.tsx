import type { InputHTMLAttributes } from "react";

export const controlStyles =
  "w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm placeholder:text-gray-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 aria-[invalid=true]:border-red-400 aria-[invalid=true]:ring-red-400 [color-scheme:light]";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${controlStyles} ${className ?? ""}`} {...props} />;
}
