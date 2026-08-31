import type { InputHTMLAttributes } from "react";

export const controlStyles =
  "w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 aria-[invalid=true]:border-red-400 aria-[invalid=true]:ring-red-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 dark:placeholder:text-gray-500";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${controlStyles} ${className ?? ""}`} {...props} />;
}
