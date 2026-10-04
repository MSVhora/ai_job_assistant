"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { useChangeTemplate, useRefit, useRegenerate } from "@/hooks/use-resume-documents";
import type { ResumeDocument, ResumeTemplate } from "@/lib/api";

import { TEMPLATE_OPTIONS } from "./create-form-schema";
import { ExportMenu } from "./ExportMenu";
import { FitSummary } from "./FitSummary";

export function DocumentHeader({ document }: { document: ResumeDocument }) {
  const regenerate = useRegenerate(document.id);
  const changeTemplate = useChangeTemplate(document.id);
  const refit = useRefit(document.id);
  const busy = regenerate.isPending || changeTemplate.isPending || refit.isPending;
  const { warnings, private_bullet_count: privateCount } = document.generation;

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <Link
              href="/resume-builder"
              className="text-xs font-semibold text-violet-700 underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
            >
              ← All resumes
            </Link>
            <h1 className="text-xl font-bold text-gray-900">{document.title}</h1>
            <p className="text-xs text-gray-500">Version {document.version}</p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label
                htmlFor="resume-template-switch"
                className="text-xs font-semibold text-gray-500"
              >
                Template
              </label>
              <Select
                id="resume-template-switch"
                value={document.template}
                disabled={busy}
                onChange={(event) => {
                  changeTemplate.mutate(event.target.value as ResumeTemplate, {
                    onSuccess: () => {
                      refit.mutate(undefined);
                    },
                  });
                }}
              >
                {TEMPLATE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.value === "classic" ? "Classic" : "Compact"}
                  </option>
                ))}
              </Select>
            </div>
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={() => {
                regenerate.mutate(undefined);
              }}
            >
              {regenerate.isPending ? "Regenerating…" : "Regenerate all"}
            </Button>
          </div>
        </div>
        <FitSummary document={document} />
        <ExportMenu documentId={document.id} />
        {privateCount > 0 && (
          <p className="text-xs text-amber-800">
            {privateCount === 1 ? "1 bullet comes" : `${String(privateCount)} bullets come`} from
            private repositories. They are marked on this screen only — copies and the PDF carry no
            marks. To leave them out, create a new resume with the exclusion turned on.
          </p>
        )}
        {warnings.length > 0 && (
          <ul
            role="status"
            className="flex flex-col gap-1 rounded-xl bg-amber-50 p-3 text-xs text-amber-900"
          >
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
