"use client";

import type { ResumeDocument } from "@/lib/api";
import { notIncludedRows } from "@/lib/resume-view";

import { CommentsPanel } from "./CommentsPanel";
import { ConflictsPanel } from "./ConflictsPanel";
import { DocumentHeader } from "./DocumentHeader";
import { GapsPanel } from "./GapsPanel";
import { NotIncludedList } from "./NotIncludedList";
import { OmittedRoles } from "./OmittedRoleCard";
import { PdfStep } from "./PdfStep";
import { ReviewSections } from "./ReviewSections";

export function DocumentView({ document }: { document: ResumeDocument }) {
  return (
    <div className="flex flex-col gap-5">
      <DocumentHeader document={document} />
      <ReviewSections document={document} />
      <CommentsPanel document={document} />
      <NotIncludedList documentId={document.id} rows={notIncludedRows(document)} />
      <OmittedRoles document={document} />
      <GapsPanel gaps={document.generation.gaps} />
      <ConflictsPanel
        documentId={document.id}
        profileId={document.profile_id}
        version={document.version}
      />
      <PdfStep document={document} />
    </div>
  );
}
