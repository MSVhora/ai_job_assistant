export function CloseIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-4 w-4">
      <path d="M6.3 5a1 1 0 00-1.3 1.3L8.6 10l-3.6 3.7A1 1 0 006.3 15L10 11.4 13.7 15a1 1 0 001.3-1.3L11.4 10 15 6.3A1 1 0 0013.7 5L10 8.6 6.3 5z" />
    </svg>
  );
}

export const JOB_TYPE_LABELS: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
  temporary: "Temporary",
};

export const REMOTE_TYPE_LABELS: Record<string, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  on_site: "On-site",
};

export function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-gray-50/80 px-3 py-2">
      <span className="text-[11px] font-semibold tracking-wide text-gray-500 uppercase">
        {label}
      </span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

export function ScoreRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span className="text-gray-600">{label}</span>
      <span className="font-semibold text-gray-900">{value}</span>
    </div>
  );
}
