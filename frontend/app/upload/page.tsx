import { BackendStatus } from "@/components/features/BackendStatus";
import { ResumeUploadForm } from "@/components/features/ResumeUploadForm";
import Link from "next/link";

export const metadata = {
  title: "Upload your resume",
  description: "Upload a resume, review the AI-drafted profile, and save it as a track.",
};

export default function UploadPage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-transparent" />
        <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-violet-300/40 blur-3xl" />
        <div className="absolute -right-24 top-32 h-72 w-72 rounded-full bg-fuchsia-300/30 blur-3xl" />
      </div>

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 px-6 pb-16 pt-14">
        <section className="flex flex-col items-center gap-3 text-center">
          <p className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-wide text-violet-700 shadow-sm shadow-violet-100">
            Step 1 of 2
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Upload your{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              resume
            </span>
          </h1>
          <p className="max-w-xl text-base text-gray-600">
            Upload a resume and AI drafts your profile — you review it in step 2 before anything is saved.
          </p>
        </section>

        <section
          id="upload"
          className="scroll-mt-24 rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur sm:p-8"
          aria-labelledby="upload-heading"
        >
          <h2 id="upload-heading" className="sr-only">
            Upload form
          </h2>
          <ResumeUploadForm />
        </section>

        <p className="text-center text-sm text-gray-600">
          Want to review or merge an existing draft?{" "}
          <Link
            href="/profile"
            className="font-semibold text-violet-700 underline underline-offset-2 hover:text-violet-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
          >
            Go to your profiles
          </Link>
        </p>
        <BackendStatus />
      </div>
    </main>
  );
}
