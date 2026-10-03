import Link from "next/link";

import { CheckIcon } from "./icons";
import type { GetStartedOption } from "./options";

export function OptionCard({ option }: { option: GetStartedOption }) {
  return option.disabled ? (
    <div
      aria-disabled="true"
      className="relative flex flex-col rounded-3xl border border-gray-200 bg-gray-50/80 p-5 text-left"
    >
      <span className="absolute top-4 right-4 rounded-full bg-gray-200 px-2.5 py-1 text-[10px] font-bold tracking-wider text-gray-500 uppercase">
        Coming soon
      </span>
      <p className="text-[11px] font-semibold tracking-wider text-gray-400 uppercase">
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
        className="absolute top-4 right-4 flex h-6 w-6 items-center justify-center rounded-full border-2 border-gray-300 text-transparent transition-colors group-hover:border-violet-600 group-hover:bg-violet-600 group-hover:text-white"
      >
        <CheckIcon />
      </span>
      <p className="text-[11px] font-semibold tracking-wider text-gray-500 uppercase">
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
  );
}
