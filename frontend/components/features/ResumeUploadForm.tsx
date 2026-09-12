"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { useExtractResume, useUploadAndExtract } from "@/hooks/use-upload-and-extract";
import { ExtractionFailedError } from "@/lib/api";

function UploadCloudIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-8 w-8">
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

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3.5 w-3.5">
      <path
        fillRule="evenodd"
        d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.8 3.8 6.8-6.8a1 1 0 011.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

const STAGES = [
  { label: "Uploading resume", end: 35 },
  { label: "Reading your resume", end: 60 },
  { label: "Drafting your profile with AI", end: 90 },
  { label: "Almost done", end: 100 },
] as const;

const ACCEPTED = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export function ResumeUploadForm() {
  const router = useRouter();
  const uploadAndExtract = useUploadAndExtract();
  const retryExtract = useExtractResume();
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const extractFailure =
    uploadAndExtract.error instanceof ExtractionFailedError ? uploadAndExtract.error : null;
  const pending = uploadAndExtract.isPending || retryExtract.isPending;
  const showProgress = uploadAndExtract.isPending || (retryExtract.isPending && progress > 0);
  const stageIndex = STAGES.findIndex((stage) => progress < stage.end);
  const currentStage = STAGES[stageIndex === -1 ? STAGES.length - 1 : stageIndex];

  useEffect(() => {
    if (!showProgress) {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }
    timerRef.current = setInterval(() => {
      setProgress((current) => Math.min(current + 1, 95));
    }, 300);
    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [showProgress]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (file === null) return;
    setProgress(0);
    uploadAndExtract.mutate(file, {
      onSuccess: (draft) => {
        setProgress(100);
        router.push(`/profile?resume=${draft.resume_id}`);
      },
    });
  };

  const acceptFile = (candidate: File | null | undefined) => {
    if (candidate) setFile(candidate);
  };

  const onDrop = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setDragging(false);
    acceptFile(event.dataTransfer.files?.[0]);
  };

  const formatSize = (bytes: number) =>
    bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

  return (
    <form onSubmit={onSubmit} className="flex w-full flex-col gap-4" noValidate>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        disabled={pending}
        aria-label="Choose a resume file (PDF or DOCX) to upload"
        className={`group flex w-full flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed px-6 py-12 text-center transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:cursor-not-allowed disabled:opacity-60 ${
          dragging
            ? "border-violet-500 bg-violet-50/80"
            : "border-violet-200 bg-violet-50/40 hover:border-violet-400 hover:bg-violet-50"
        }`}
      >
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-lg shadow-violet-200 transition-transform group-hover:scale-110">
          <UploadCloudIcon />
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            className="hidden"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              acceptFile(event.target.files?.[0] ?? null);
              event.target.value = "";
            }}
          />
        </span>
        <span className="text-base font-semibold text-gray-900">
          Drop your resume here, or <span className="text-violet-700">browse</span>
        </span>
        <span className="text-sm text-gray-500">PDF or DOCX · up to a few MB</span>
      </button>

      {file !== null && (
        <div className="flex items-center gap-3 rounded-2xl border border-violet-100 bg-white p-3 shadow-sm">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-600">
            <FileIcon />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-gray-900">{file.name}</span>
            <span className="block text-xs text-gray-500">{formatSize(file.size)}</span>
          </span>
          <Button
            type="button"
            variant="secondary"
            className="px-2 py-1 text-xs"
            disabled={pending}
            onClick={() => setFile(null)}
          >
            Remove
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          disabled={file === null || pending}
          className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 py-2.5 font-semibold shadow-lg shadow-violet-200 hover:from-violet-700 hover:to-fuchsia-700"
        >
          {uploadAndExtract.isPending ? "Extracting profile…" : "Upload & review"}
        </Button>
        <p aria-live="polite" className="text-sm text-gray-500">
          {uploadAndExtract.isPending
            ? "Parsing the resume and drafting your profile — this can take a few seconds."
            : "Your AI-drafted profile opens for review before anything is saved."}
        </p>
      </div>

      {showProgress && (
        <div
          role="status"
          aria-live="polite"
          className="flex flex-col gap-2 rounded-2xl border border-violet-100 bg-white p-4 shadow-sm"
        >
          <div className="flex items-center justify-between text-sm">
            <span className="font-semibold text-gray-900">{currentStage.label}…</span>
            <span className="font-semibold text-violet-700">{progress}%</span>
          </div>
          <div
            className="h-2.5 w-full overflow-hidden rounded-full bg-violet-100"
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Extraction progress"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <ol className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {STAGES.map((stage, index) => {
              const done = progress >= stage.end;
              const active = index === stageIndex;
              return (
                <li
                  key={stage.label}
                  className={`flex items-center gap-1 ${
                    done ? "text-emerald-600" : active ? "font-semibold text-violet-700" : "text-gray-400"
                  }`}
                >
                  {done ? <CheckIcon /> : <span aria-hidden>{index + 1}.</span>}
                  {stage.label}
                </li>
              );
            })}
          </ol>
        </div>
      )}

      {extractFailure !== null && (
        <div className="flex flex-col gap-2 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          <p>The resume uploaded, but extraction didn&apos;t complete. You can retry without re-uploading.</p>
          {retryExtract.error !== null && <p role="alert">{retryExtract.error.message}</p>}
          <div>
            <Button
              type="button"
              variant="secondary"
              disabled={pending}
              onClick={() => {
                setProgress(0);
                retryExtract.mutate(extractFailure.resumeId, {
                  onSuccess: (draft) => {
                    setProgress(100);
                    router.push(`/profile?resume=${draft.resume_id}`);
                  },
                });
              }}
            >
              {retryExtract.isPending ? "Extracting…" : "Extract again"}
            </Button>
          </div>
        </div>
      )}
    </form>
  );
}
