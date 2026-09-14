"use client";

import type { ReactNode } from "react";

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className={`h-4 w-4 shrink-0 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
    >
      <path
        fillRule="evenodd"
        d="M5.3 7.3a1 1 0 011.4 0L10 10.6l3.3-3.3a1 1 0 111.4 1.4l-4 4a1 1 0 01-1.4 0l-4-4a1 1 0 010-1.4z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function Accordion({
  id,
  open,
  onToggle,
  trigger,
  children,
}: {
  id: string;
  open: boolean;
  onToggle: () => void;
  trigger: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={`${id}-content`}
        className="flex w-full flex-wrap items-center gap-2 px-3 py-2.5 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
      >
        {trigger}
        <ChevronIcon open={open} />
      </button>
      {open && (
        <div id={`${id}-content`} role="region" className="flex flex-col gap-2.5 border-t border-gray-100 p-3">
          {children}
        </div>
      )}
    </div>
  );
}
