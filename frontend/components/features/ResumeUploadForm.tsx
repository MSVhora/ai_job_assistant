"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useExtractResume, useUploadAndExtract } from "@/hooks/use-upload-and-extract";
import { ExtractionFailedError } from "@/lib/api";

export function ResumeUploadForm() {
  const router = useRouter();
  const uploadAndExtract = useUploadAndExtract();
  const retryExtract = useExtractResume();
  const [file, setFile] = useState<File | null>(null);

  const extractFailure =
    uploadAndExtract.error instanceof ExtractionFailedError ? uploadAndExtract.error : null;
  const pending = uploadAndExtract.isPending || retryExtract.isPending;

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (file === null) return;
    uploadAndExtract.mutate(file, {
      onSuccess: (draft) => {
        router.push(`/profile?resume=${draft.resume_id}`);
      },
    });
  };

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-md flex-col gap-3" noValidate>
      <Field
        label="Resume (PDF or DOCX)"
        htmlFor="resume-file"
        error={extractFailure !== null ? undefined : uploadAndExtract.error?.message}
      >
        <Input
          id="resume-file"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          aria-invalid={uploadAndExtract.error ? true : undefined}
        />
      </Field>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={file === null || pending}>
          {uploadAndExtract.isPending ? "Extracting profile…" : "Upload & review"}
        </Button>
        <p aria-live="polite" className="text-sm text-gray-600 dark:text-gray-400">
          {uploadAndExtract.isPending
            ? "Parsing the resume and drafting your profile — this can take a few seconds."
            : "Your AI-drafted profile opens for review before anything is saved."}
        </p>
      </div>
      {extractFailure !== null && (
        <div className="flex flex-col gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
          <p>The resume uploaded, but extraction didn&apos;t complete. You can retry without re-uploading.</p>
          {retryExtract.error !== null && <p role="alert">{retryExtract.error.message}</p>}
          <div>
            <Button
              type="button"
              variant="secondary"
              disabled={pending}
              onClick={() =>
                retryExtract.mutate(extractFailure.resumeId, {
                  onSuccess: (draft) => {
                    router.push(`/profile?resume=${draft.resume_id}`);
                  },
                })
              }
            >
              {retryExtract.isPending ? "Extracting…" : "Extract again"}
            </Button>
          </div>
        </div>
      )}
    </form>
  );
}
