import type { Metadata } from "next";

import { ResumeDocumentPageClient } from "@/components/features/resume/ResumeDocumentPageClient";

export const metadata: Metadata = {
  title: "Review resume",
  description: "Review the written resume, comment on sections, then generate a PDF.",
};

export default async function ResumeDocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-white" />
      </div>
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 pt-6 pb-12 sm:px-6">
        <ResumeDocumentPageClient id={id} />
      </div>
    </main>
  );
}
