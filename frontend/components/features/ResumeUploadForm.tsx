"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useUploadAndExtract } from "@/hooks/use-upload-and-extract";

export function ResumeUploadForm() {
  const router = useRouter();
  const uploadAndExtract = useUploadAndExtract();
  const [file, setFile] = useState<File | null>(null);

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
        error={uploadAndExtract.error ? uploadAndExtract.error.message : undefined}
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
        <Button type="submit" disabled={file === null || uploadAndExtract.isPending}>
          {uploadAndExtract.isPending ? "Extracting profile…" : "Upload & review"}
        </Button>
        <p aria-live="polite" className="text-sm text-gray-600 dark:text-gray-400">
          {uploadAndExtract.isPending
            ? "Parsing the resume and drafting your profile — this can take a few seconds."
            : "Your AI-drafted profile opens for review before anything is saved."}
        </p>
      </div>
    </form>
  );
}
