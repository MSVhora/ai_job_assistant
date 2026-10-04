"use client";

import { useEvidenceItem } from "@/hooks/use-evidence-sources";

function EvidenceChip({ itemId }: { itemId: string }) {
  const item = useEvidenceItem(itemId);
  const base =
    "inline-flex max-w-[16rem] items-center gap-1 truncate rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-700";
  if (item.isPending) return <span className={`${base} animate-pulse`}>Loading source…</span>;
  if (item.isError) return <span className={base}>Source unavailable</span>;
  const label = `${item.data.kind.replace("_", " ")}: ${item.data.title ?? "untitled"}`;
  if (item.data.url === null) return <span className={base}>{label}</span>;
  return (
    <a
      href={item.data.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`${base} text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600`}
      title={label}
    >
      {label}
    </a>
  );
}

export function EvidenceChips({ ids }: { ids: string[] }) {
  if (ids.length === 0) return null;
  return (
    <ul aria-label="Evidence" className="flex flex-wrap gap-1.5">
      {ids.map((id) => (
        <li key={id}>
          <EvidenceChip itemId={id} />
        </li>
      ))}
    </ul>
  );
}
