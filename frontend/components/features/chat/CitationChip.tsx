import type { AgentCitation } from "@/lib/api";

const STYLES: Record<AgentCitation["kind"], string> = {
  achievement: "border-violet-300 bg-violet-50 text-violet-800 hover:bg-violet-100",
  evidence: "border-sky-300 bg-sky-50 text-sky-800 hover:bg-sky-100",
  profile: "border-gray-300 bg-gray-50 text-gray-700 hover:bg-gray-100",
  job: "border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100",
};

export function CitationChip({
  citation,
  number,
  onOpen,
}: {
  citation: AgentCitation;
  number: number;
  onOpen: (citation: AgentCitation) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => {
        onOpen(citation);
      }}
      aria-label={`Source ${String(number)}: ${citation.label}`}
      title={citation.label}
      className={`mx-0.5 inline-flex min-w-6 items-center justify-center rounded-md border px-1.5 align-baseline text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 ${STYLES[citation.kind]}`}
    >
      {number}
    </button>
  );
}
