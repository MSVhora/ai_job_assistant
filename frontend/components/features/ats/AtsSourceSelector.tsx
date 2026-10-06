"use client";

import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type DragEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useProfiles } from "@/hooks/use-profiles";
import { uploadResume } from "@/lib/api";
import type { AtsSourceMode } from "@/components/features/ats/AtsScoreForm";

const ACCEPTED =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

type SourceSelectorProps = {
  mode: AtsSourceMode;
  onModeChange: (mode: AtsSourceMode) => void;
  onResumePicked: (resumeId: string, filename: string) => void;
  onProfilePicked: (profileId: string, label: string) => void;
  onSelectionCleared: () => void;
};

function UploadCloudIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-7 w-7">
      <path d="M12 16V8m0 0l-3 3m3-3l3 3" />
      <path d="M6.5 19a4.5 4.5 0 01-.4-8.98 6 6 0 0111.66-1.6A4.25 4.25 0 0117.75 19H6.5z" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" />
      <path d="M14 3v5h5" />
    </svg>
  );
}

export function AtsSourceSelector({
  mode,
  onModeChange,
  onResumePicked,
  onProfilePicked,
  onSelectionCleared,
}: SourceSelectorProps) {
  const profilesQuery = useProfiles();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => uploadResume(file),
    onSuccess: (uploaded) => {
      setSelectedFilename(uploaded.original_filename);
      onResumePicked(uploaded.resume_id, uploaded.original_filename);
    },
    onError: () => setSelectedFilename(null),
  });

  const profiles = (profilesQuery.data ?? []).flatMap((profile) => {
    if (profile.profile_id === undefined || profile.profile_id === null) return [];
    return [
      {
        profile_id: profile.profile_id,
        name: profile.name,
        source_resume_filename: profile.source_resume_filename,
        updated_at: profile.updated_at,
      },
    ];
  });

  const toggleMode = (next: AtsSourceMode) => {
    if (next !== mode) {
      setSelectedFilename(null);
      setSelectedProfileId(null);
      onSelectionCleared();
    }
    onModeChange(next);
  };

  const onDrop = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) upload.mutate(file);
  };

  const tabClass = (active: boolean) =>
    `rounded-full px-5 py-2 text-sm font-semibold transition-all ${
      active
        ? "bg-white text-violet-700 shadow-sm ring-1 ring-violet-200"
        : "text-gray-500 hover:text-gray-700"
    }`;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex w-fit gap-1 rounded-full bg-violet-50 p-1" role="tablist" aria-label="Resume source">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "resume"}
          className={tabClass(mode === "resume")}
          onClick={() => toggleMode("resume")}
        >
          Upload a resume
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "profile"}
          className={tabClass(mode === "profile")}
          onClick={() => toggleMode("profile")}
        >
          Use a saved profile
        </button>
      </div>

      {mode === "resume" ? (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            disabled={upload.isPending}
            aria-label="Choose a resume file (PDF or DOCX) to score"
            className={`flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-60 ${
              dragging
                ? "border-violet-500 bg-violet-50"
                : "border-violet-200 bg-violet-50/50 hover:border-violet-400 hover:bg-violet-50"
            }`}
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
              <UploadCloudIcon />
            </span>
            <span className="text-sm font-semibold text-gray-900">
              {upload.isPending
                ? "Parsing your resume…"
                : "Drop your resume here, or browse"}
            </span>
            <span className="text-xs text-gray-500">PDF or DOCX · parsed for scoring, not saved as a profile</span>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED}
              className="hidden"
              tabIndex={-1}
              aria-hidden="true"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
                event.target.value = "";
              }}
            />
          </button>
          {selectedFilename !== null && (
            <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
                <FileIcon />
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-900">
                {selectedFilename}
              </span>
              <Button
                type="button"
                variant="secondary"
                className="px-2 py-1 text-xs"
                disabled={upload.isPending}
                onClick={() => {
                  setSelectedFilename(null);
                  onSelectionCleared();
                }}
              >
                Remove
              </Button>
            </div>
          )}
          {upload.isError && (
            <p role="alert" className="text-sm text-red-600">
              {upload.error.message}
            </p>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {profilesQuery.isPending && <p className="text-sm text-gray-500">Loading profiles…</p>}
          {profilesQuery.isError && (
            <p role="alert" className="text-sm text-red-600">
              {profilesQuery.error.message}
            </p>
          )}
          {profilesQuery.isSuccess && profiles.length === 0 && (
            <p className="rounded-xl bg-violet-50 px-4 py-3 text-sm text-gray-600">
              No saved profiles yet — switch to &ldquo;Upload a resume&rdquo; instead.
            </p>
          )}
          <div className="grid gap-2.5 sm:grid-cols-2">
            {profiles.map((profile) => {
              const selected = selectedProfileId === profile.profile_id;
              return (
                <button
                  key={profile.profile_id}
                  type="button"
                  onClick={() => {
                    setSelectedProfileId(profile.profile_id);
                    onProfilePicked(profile.profile_id, profile.name);
                  }}
                  aria-pressed={selected}
                  className={`flex items-center justify-between gap-3 rounded-2xl border-2 px-4 py-3 text-left text-sm transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 ${
                    selected
                      ? "border-violet-500 bg-violet-50 shadow-sm"
                      : "border-gray-200 bg-white hover:border-violet-300 hover:bg-violet-50/40"
                  }`}
                >
                  <span className="min-w-0 flex-1 truncate font-semibold text-gray-900">
                    {profile.name}
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    {profile.source_resume_filename !== null && (
                      <Badge variant="neutral">
                        <span className="max-w-24 truncate">{profile.source_resume_filename}</span>
                      </Badge>
                    )}
                    <span className="text-xs text-gray-400">
                      {new Date(profile.updated_at).toLocaleDateString()}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
