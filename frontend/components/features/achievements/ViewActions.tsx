"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { EmployerGroup } from "@/lib/api";
import { choiceLabel, viewIds } from "@/lib/draft-groups";

import { GroupActionModal, type GroupAction } from "./GroupActionModal";

export function ViewActions({
  groups,
  employer,
  repository,
}: {
  groups: EmployerGroup[];
  employer: string;
  repository: string;
}) {
  const [action, setAction] = useState<GroupAction | null>(null);
  if (employer === "" && repository === "") return null;
  const ids = viewIds(groups, employer, repository);
  if (ids.drafts.length === 0) return null;
  const label = repository === "" ? choiceLabel(groups, employer) : repository;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-gray-600">
        {ids.drafts.length} drafts in this view, {ids.eligible.length} clean:
      </span>
      <Button
        variant="secondary"
        disabled={ids.eligible.length === 0}
        onClick={() => {
          setAction({ kind: "approve", label, ids: ids.eligible });
        }}
      >
        Approve {ids.eligible.length} clean
      </Button>
      <Button
        variant="secondary"
        onClick={() => {
          setAction({ kind: "reject", label, ids: ids.drafts });
        }}
      >
        Reject all {ids.drafts.length}
      </Button>
      <GroupActionModal
        action={action}
        onClose={() => {
          setAction(null);
        }}
      />
    </div>
  );
}
