"use client";

import { exportResumeDocument, type ExportFormat } from "@/lib/api";

import { CopyButton } from "./CopyButton";

const FORMATS: { format: ExportFormat; label: string }[] = [
  { format: "text", label: "Plain text" },
  { format: "markdown", label: "Markdown" },
  { format: "json_resume", label: "JSON Resume" },
];

export function ExportMenu({ documentId }: { documentId: string }) {
  return (
    <div role="group" aria-label="Copy the whole resume" className="flex flex-wrap items-center">
      <span className="mr-1 text-xs font-semibold text-gray-500">Copy whole resume:</span>
      {FORMATS.map(({ format, label }) => (
        <CopyButton
          key={format}
          label={label}
          ariaLabel={`Copy the whole resume as ${label}`}
          getText={() => exportResumeDocument(documentId, format)}
        />
      ))}
    </div>
  );
}
