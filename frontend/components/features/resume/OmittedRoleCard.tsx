"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useIncludeRole } from "@/hooks/use-resume-documents";
import type { ResumeDocument } from "@/lib/api";
import { blockTitle } from "@/lib/resume-view";

export function OmittedRoles({ document }: { document: ResumeDocument }) {
  const include = useIncludeRole(document.id);
  const omitted = document.generation.omitted_roles;
  if (omitted.length === 0) return null;

  return (
    <Card title={<h2 className="text-lg font-semibold text-gray-900">Omitted roles</h2>}>
      <ul className="flex flex-col gap-3">
        {omitted.map((role) => {
          const partner = document.content.work.find((job) => job.id === role.overlaps_with);
          const when = [role.entry.start_date, role.entry.end_date ?? "Present"]
            .filter(Boolean)
            .join(" – ");
          return (
            <li key={role.block_id} className="flex flex-col gap-1 rounded-xl bg-amber-50/60 p-3">
              <p className="text-sm text-gray-900">
                <span className="font-semibold">Omitted: {blockTitle(role.entry)}</span> ({when})
                {partner !== undefined && (
                  <>
                    {" "}
                    overlaps <span className="font-semibold">{blockTitle(partner)}</span> — kept the
                    higher-priority role.
                  </>
                )}
              </p>
              <p className="text-xs text-gray-600">{role.reason}</p>
              <div>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={include.isPending}
                  onClick={() => {
                    include.mutate(role.block_id);
                  }}
                >
                  Include anyway
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
