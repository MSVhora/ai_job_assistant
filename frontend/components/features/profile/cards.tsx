"use client";

import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

import { ChevronIcon } from "./profile-icons";

export function SectionCard({
  title,
  description,
  icon,
  badge,
  action,
  defaultOpen = true,
  hasError = false,
  children,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  badge?: ReactNode;
  action?: ReactNode;
  defaultOpen?: boolean;
  hasError?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-lg shadow-gray-100">
      <div className="flex flex-wrap items-center gap-2 border-b border-gray-100 bg-gray-50/60 px-5 py-4 sm:px-6">
        <button
          type="button"
          onClick={() => {
            setOpen((current) => !current);
          }}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-xl text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          {icon !== undefined && (
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
              {icon}
            </span>
          )}
          <span className="flex min-w-0 flex-col">
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-base font-bold tracking-tight text-gray-900">{title}</span>
              {badge}
            </span>
            {description !== undefined && (
              <span className="truncate text-xs text-gray-500">{description}</span>
            )}
          </span>
          <span className="ml-auto flex items-center gap-2 pl-2">
            <ChevronIcon open={open} />
          </span>
        </button>
        {action !== undefined && <div className="flex shrink-0 items-center">{action}</div>}
      </div>
      {hasError && !open && (
        <p
          role="alert"
          className="border-b border-red-100 bg-red-50 px-6 py-2 text-xs font-medium text-red-700"
        >
          This section has fields that need attention — reopen to review them.
        </p>
      )}
      <div className={open ? "p-5 sm:p-6" : "hidden"}>{children}</div>
    </section>
  );
}

export function ItemCard({
  title,
  subtitle,
  index,
  count,
  onRemove,
  onMove,
  children,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  index: number;
  count: number;
  onRemove: () => void;
  onMove: (from: number, to: number) => void;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50/50 p-4 transition-colors focus-within:border-violet-300 hover:border-violet-200">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-100 text-[11px] font-bold text-violet-700">
            {index + 1}
          </span>
          <div className="min-w-0">
            {title !== undefined && (
              <p className="truncate text-sm font-semibold text-gray-900">{title}</p>
            )}
            {subtitle !== undefined && <p className="truncate text-xs text-gray-500">{subtitle}</p>}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button
            variant="secondary"
            className="rounded-full px-2.5 py-1 text-xs"
            onClick={() => {
              onMove(index, index - 1);
            }}
            disabled={index === 0}
            aria-label="Move up"
          >
            ↑
          </Button>
          <Button
            variant="secondary"
            className="rounded-full px-2.5 py-1 text-xs"
            onClick={() => {
              onMove(index, index + 1);
            }}
            disabled={index === count - 1}
            aria-label="Move down"
          >
            ↓
          </Button>
          <Button
            variant="danger"
            className="rounded-full px-3 py-1 text-xs"
            onClick={onRemove}
            aria-label="Remove entry"
          >
            Remove
          </Button>
        </div>
      </div>
      {children}
    </div>
  );
}

export function EmptyState({ message, action }: { message: string; action: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-violet-200 bg-violet-50/40 px-4 py-6 text-center">
      <p className="text-sm text-gray-500">{message}</p>
      {action}
    </div>
  );
}

export const addButtonClass =
  "rounded-full border-dashed px-4 py-1.5 text-xs font-semibold text-violet-700 hover:border-violet-400 hover:bg-violet-50";
