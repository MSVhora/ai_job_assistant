import type { ReactNode } from "react";

type BadgeVariant =
  | "neutral"
  | "success"
  | "warn"
  | "danger"
  | "ai"
  | "official-api"
  | "third-party-scraper";

const variantStyles: Record<BadgeVariant, string> = {
  neutral: "border-gray-300 bg-gray-50 text-gray-700",
  success: "border-emerald-300 bg-emerald-50 text-emerald-800",
  warn: "border-amber-300 bg-amber-50 text-amber-800",
  danger: "border-red-300 bg-red-50 text-red-800",
  ai: "border-sky-300 bg-sky-50 text-sky-800",
  "official-api": "border-emerald-300 bg-emerald-50 text-emerald-800",
  "third-party-scraper": "border-amber-300 bg-amber-50 text-amber-800",
};

export function Badge({
  variant = "neutral",
  children,
}: {
  variant?: BadgeVariant;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${variantStyles[variant]}`}
    >
      {children}
    </span>
  );
}
