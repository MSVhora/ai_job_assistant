"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { StructuredProfile } from "@/lib/api";

import { AiExtractedBadge, SectionCard } from "./fields";
import { SaveStatus } from "./SaveStatus";

const FIELD_KEYS = [
  "contact",
  "headline",
  "summary",
  "skills",
  "experience",
  "projects",
  "education",
  "certifications",
  "awards",
  "extra_sections",
  "preferences",
] as const;

type FieldKey = (typeof FIELD_KEYS)[number];

const FIELD_LABELS: Record<FieldKey, string> = {
  contact: "Contact",
  headline: "Headline",
  summary: "Summary",
  skills: "Skills",
  experience: "Experience",
  projects: "Projects",
  education: "Education",
  certifications: "Certifications",
  awards: "Awards",
  extra_sections: "Extra sections",
  preferences: "Preferences",
};

function summarize(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not set";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? "Not set" : `${value.length} entr${value.length === 1 ? "y" : "ies"}`;
  }
  const filled = Object.values(value).filter(
    (entry) => entry !== null && entry !== undefined && entry !== "",
  );
  return filled.length === 0 ? "Not set" : `${filled.length} field(s) set`;
}

function valuesEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function MergeDiffPanel({
  current,
  draft,
  isSaving,
  saveError,
  savedRevisionSource,
  onSave,
  onDiscard,
}: {
  current: StructuredProfile;
  draft: StructuredProfile;
  isSaving: boolean;
  saveError: string | null;
  savedRevisionSource: string | null;
  onSave: (merged: StructuredProfile) => void;
  onDiscard: () => void;
}) {
  const [takenDraft, setTakenDraft] = useState<ReadonlySet<FieldKey>>(new Set());

  const differing = FIELD_KEYS.filter((key) => !valuesEqual(current[key], draft[key]));

  const toggle = (key: FieldKey) => {
    setTakenDraft((previous) => {
      const next = new Set(previous);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const saveMerged = () => {
    const merged = { ...current } as Record<FieldKey, unknown>;
    for (const key of takenDraft) {
      merged[key] = draft[key];
    }
    onSave(merged as unknown as StructuredProfile);
  };

  return (
    <SectionCard
      title="Merge re-uploaded draft"
      action={
        <Button variant="secondary" onClick={onDiscard} disabled={isSaving}>
          Discard draft
        </Button>
      }
    >
      <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
        Your saved profile is compared with the AI draft from the re-uploaded resume. Nothing
        changes until you save — choose per field whether to keep the current value or take the
        draft&apos;s suggestion.
      </p>
      {differing.length === 0 ? (
        <p className="text-sm text-gray-600 dark:text-gray-400">
          The draft matches your saved profile — no decisions needed.
        </p>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Button
              variant="secondary"
              onClick={() => setTakenDraft(new Set(differing))}
              disabled={isSaving}
            >
              Use all draft values
            </Button>
            <Button variant="secondary" onClick={() => setTakenDraft(new Set())} disabled={isSaving}>
              Keep all current values
            </Button>
            <AiExtractedBadge />
          </div>
          <ul className="flex flex-col gap-3">
            {differing.map((key) => (
              <li
                key={key}
                className="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
                aria-label={FIELD_LABELS[key]}
              >
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {FIELD_LABELS[key]}
                  </span>
                  <div className="flex gap-1" role="group" aria-label={`Choose value for ${FIELD_LABELS[key]}`}>
                    <Button
                      variant={takenDraft.has(key) ? "secondary" : "primary"}
                      className="px-2 py-1"
                      aria-pressed={!takenDraft.has(key)}
                      onClick={() => toggle(key)}
                      disabled={isSaving}
                    >
                      Keep current
                    </Button>
                    <Button
                      variant={takenDraft.has(key) ? "primary" : "secondary"}
                      className="px-2 py-1"
                      aria-pressed={takenDraft.has(key)}
                      onClick={() => toggle(key)}
                      disabled={isSaving}
                    >
                      Use draft
                    </Button>
                  </div>
                </div>
                <div className="grid gap-2 text-sm sm:grid-cols-2">
                  <p className="rounded-md bg-gray-50 px-3 py-2 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                    <Badge variant="neutral">current</Badge>{" "}
                    <span className="ml-1">{summarize(current[key])}</span>
                  </p>
                  <p className="rounded-md bg-sky-50 px-3 py-2 text-gray-700 dark:bg-sky-950 dark:text-gray-300">
                    <Badge variant="ai">draft</Badge>{" "}
                    <span className="ml-1">{summarize(draft[key])}</span>
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="mt-6 flex items-center justify-between gap-3 border-t border-gray-100 pt-4 dark:border-gray-800">
        <SaveStatus isSaving={isSaving} error={saveError} savedRevisionSource={savedRevisionSource} />
        <Button onClick={saveMerged} disabled={isSaving || differing.length === 0}>
          {isSaving ? "Saving…" : "Save merged profile"}
        </Button>
      </div>
    </SectionCard>
  );
}
