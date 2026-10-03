"use client";

import { Badge } from "@/components/ui/badge";
import { useEvidenceItem } from "@/hooks/use-evidence-sources";
import type { EvidenceLink } from "@/lib/api";

export function EvidenceItemView({
  link,
  selectable,
  selected,
  onSelect,
  onUnlink,
  busy,
}: {
  link: EvidenceLink;
  selectable: boolean;
  selected: boolean;
  onSelect: (selected: boolean) => void;
  onUnlink: () => void;
  busy: boolean;
}) {
  const item = useEvidenceItem(link.item_id);
  return (
    <li className="rounded-xl border border-gray-200 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {selectable && (
          <input
            type="checkbox"
            aria-label={`Move ${item.data?.title ?? "this evidence"} to a new achievement`}
            checked={selected}
            onChange={(event) => {
              onSelect(event.target.checked);
            }}
            className="h-4 w-4 rounded border-gray-300 text-violet-600"
          />
        )}
        <Badge variant={link.role === "primary" ? "success" : "neutral"}>{link.role}</Badge>
        {item.data !== undefined && <Badge>{item.data.kind.replace("_", " ")}</Badge>}
        {item.data?.is_private === true && <Badge variant="warn">Private repo</Badge>}
        <button
          type="button"
          disabled={busy}
          onClick={onUnlink}
          className="ml-auto text-xs font-semibold text-red-700 hover:underline disabled:opacity-50"
        >
          Unlink
        </button>
      </div>
      {item.isPending && <p className="mt-2 text-xs text-gray-500">Loading the source…</p>}
      {item.isError && <p className="mt-2 text-xs text-red-700">The source could not be loaded.</p>}
      {item.data !== undefined && (
        <>
          <p className="mt-2 font-semibold text-gray-900">
            {item.data.url !== null ? (
              <a
                href={item.data.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-violet-700 underline"
              >
                {item.data.title ?? item.data.external_id}
              </a>
            ) : (
              (item.data.title ?? item.data.external_id)
            )}
          </p>
          <p className="mt-1 line-clamp-4 whitespace-pre-wrap text-gray-600">{item.data.body}</p>
        </>
      )}
      {link.quote !== null && (
        <p className="mt-2 border-l-2 border-violet-300 pl-2 text-xs text-gray-700">
          Quote: “{link.quote}”
        </p>
      )}
    </li>
  );
}
