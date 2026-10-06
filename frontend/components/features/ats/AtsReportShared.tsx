import type { ReactNode } from "react";

export function scoreTone(score: number): { bar: string; text: string; ring: string } {
  if (score >= 80) return { bar: "bg-emerald-500", text: "text-emerald-700", ring: "bg-emerald-500" };
  if (score >= 60) return { bar: "bg-amber-500", text: "text-amber-700", ring: "bg-amber-500" };
  return { bar: "bg-red-500", text: "text-red-700", ring: "bg-red-500" };
}

export function SectionCard({
  title,
  count,
  accent = "gray",
  icon,
  children,
}: {
  title: string;
  count?: number;
  accent?: "gray" | "emerald" | "amber" | "violet";
  icon: ReactNode;
  children: ReactNode;
}) {
  const accents: Record<string, string> = {
    gray: "text-gray-500",
    emerald: "text-emerald-700",
    amber: "text-amber-700",
    violet: "text-violet-700",
  };
  return (
    <div className="flex flex-col gap-4 rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-bold text-gray-900">
          <span className={`flex h-7 w-7 items-center justify-center text-current ${accents[accent]}`}>
            {icon}
          </span>
          {title}
        </h3>
        {count !== undefined && count > 0 && (
          <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-600">
            {count}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}
