"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useUnmergeEmployer } from "@/hooks/use-employers";
import { useEmployers } from "@/hooks/use-evidence-sync";

import { AddEmployerDialog } from "./AddEmployerDialog";
import { MergeChooserModal } from "./MergeChooserModal";
import { MergeSuggestionsModal } from "./MergeSuggestionsModal";

export function EmployersPanel() {
  const employers = useEmployers();
  const unmerge = useUnmergeEmployer();
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [adding, setAdding] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [merging, setMerging] = useState<string[]>([]);

  const groups = (employers.data ?? []).filter((option) => option.kind === "experience");
  const toggle = (key: string, value: boolean) => {
    setSelected((current) => {
      const next = new Set(current);
      if (value) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  return (
    <Card
      title={<h2 className="text-base font-bold text-gray-900">Employers</h2>}
      action={
        <div className="flex gap-2">
          <Button
            variant="secondary"
            disabled={groups.length < 2}
            onClick={() => {
              setSuggesting(true);
            }}
          >
            Suggest merges
          </Button>
          <Button
            onClick={() => {
              setAdding(true);
            }}
          >
            Add an employer
          </Button>
        </div>
      }
    >
      <p className="mb-3 text-xs text-gray-600">
        Roles at the same company are one employer. If two names are the same company written
        differently, merge them so their work counts together. Employers come from your profiles;
        add one here if it is not on your resume.
      </p>
      {employers.isPending && <div className="h-16 animate-pulse rounded-xl bg-gray-100" />}
      {employers.isError && (
        <p role="alert" className="text-sm text-red-700">
          Could not load your employers: {employers.error.message}
        </p>
      )}
      {employers.isSuccess && groups.length === 0 && (
        <p className="text-sm text-gray-600">
          No employers yet — they come from your profile&apos;s experience.
        </p>
      )}
      <ul className="flex flex-col gap-2" aria-label="Employers">
        {groups.map((group) => (
          <li
            key={group.key}
            className="flex flex-wrap items-center gap-2 rounded-xl border border-gray-200 p-3"
          >
            <input
              type="checkbox"
              aria-label={`Select ${group.company ?? group.label} to merge`}
              checked={selected.has(group.key)}
              onChange={(event) => {
                toggle(group.key, event.target.checked);
              }}
              className="h-4 w-4 rounded border-gray-300 text-violet-600"
            />
            <span className="text-sm font-semibold text-gray-900">{group.label}</span>
            {(group.merged_from ?? []).map((name) => (
              <Badge key={name}>Merged: {name}</Badge>
            ))}
            {(group.merged_from ?? []).length > 0 && (
              <button
                type="button"
                disabled={unmerge.isPending}
                onClick={() => {
                  unmerge.mutate(group.key, {
                    onSuccess: () => {
                      toast.success(`Unmerged ${group.company ?? ""}`);
                    },
                  });
                }}
                className="ml-auto rounded-full px-3 py-1 text-xs font-semibold text-red-700 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
              >
                Unmerge
              </button>
            )}
          </li>
        ))}
      </ul>
      {selected.size >= 2 && (
        <div className="mt-3">
          <Button
            onClick={() => {
              setMerging(
                groups
                  .filter((group) => selected.has(group.key))
                  .flatMap((group) => (group.company ? [group.company] : [])),
              );
            }}
          >
            Merge {selected.size} selected…
          </Button>
        </div>
      )}
      <AddEmployerDialog
        open={adding}
        onClose={() => {
          setAdding(false);
        }}
      />
      <MergeSuggestionsModal
        open={suggesting}
        onClose={() => {
          setSuggesting(false);
        }}
      />
      <MergeChooserModal
        key={merging.join("|")}
        names={merging}
        onClose={() => {
          setMerging([]);
          setSelected(new Set());
        }}
      />
    </Card>
  );
}
