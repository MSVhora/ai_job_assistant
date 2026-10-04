"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useResumePdf } from "@/hooks/use-resume-pdf";
import type { ResumeDocument } from "@/lib/api";

export function PdfStep({ document }: { document: ResumeDocument }) {
  const { state, generate } = useResumePdf(document.id, document.version);
  const stale = state.status === "ready" && state.version !== document.version;

  return (
    <Card title={<h2 className="text-lg font-semibold text-gray-900">PDF</h2>}>
      <p className="mb-3 text-xs text-gray-600">
        Nothing is rendered until you ask. Generating re-fits the current content to{" "}
        {document.page_target} page{document.page_target === 1 ? "" : "s"} first. Private-repo marks
        are for this screen only and never appear in the file.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" disabled={state.status === "pending"} onClick={() => void generate()}>
          {state.status === "pending" ? "Generating…" : "Generate PDF"}
        </Button>
        {state.status === "ready" && (
          <a
            href={state.url}
            download="resume.pdf"
            className="rounded-full border border-violet-300 px-4 py-2 text-sm font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Download
          </a>
        )}
      </div>
      <div aria-live="polite" className="mt-3">
        {state.status === "error" && (
          <p role="alert" className="text-sm text-red-700">
            {state.message}
          </p>
        )}
        {stale && (
          <p className="text-xs font-medium text-amber-800">
            The resume changed after this PDF was made — generate it again.
          </p>
        )}
      </div>
      {state.status === "ready" && (
        <iframe
          title="Resume PDF preview"
          src={state.url}
          className="mt-3 h-[70vh] w-full rounded-xl border border-gray-200"
        />
      )}
    </Card>
  );
}
