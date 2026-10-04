import type { ResumeDocument } from "@/lib/api";
import { availableCount, notIncludedRows, pageUsageLine } from "@/lib/resume-view";

const PRESET_NAMES: Record<string, string> = {
  P0: "Comfortable",
  P1: "Medium",
  P2: "Tight",
};

export function FitSummary({ document }: { document: ResumeDocument }) {
  const { layout } = document;
  const available = availableCount(notIncludedRows(document));
  const type =
    layout.preset && layout.font_pt
      ? `${PRESET_NAMES[layout.preset] ?? layout.preset} spacing, ${String(layout.font_pt)} pt`
      : null;
  return (
    <div className="flex flex-col gap-1 text-sm text-gray-700" aria-live="polite">
      <p className="font-medium">{pageUsageLine(document, available)}</p>
      {type !== null && <p className="text-xs text-gray-500">{type}</p>}
      {layout.steps.length > 0 && (
        <details className="text-xs text-gray-500">
          <summary className="cursor-pointer">How the fit decided</summary>
          <ul className="mt-1 list-disc pl-4">
            {layout.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
