import { BackendStatus } from "@/components/features/BackendStatus";
import { AtsScoreForm } from "@/components/features/ats/AtsScoreForm";

export const metadata = {
  title: "AI ATS Score",
  description: "Score your resume or a saved profile against a job description and fix the gaps.",
};

export default function AtsScorePage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-transparent" />
        <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-violet-300/40 blur-3xl" />
        <div className="absolute -right-24 top-32 h-72 w-72 rounded-full bg-fuchsia-300/30 blur-3xl" />
      </div>

      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-6 pb-16 pt-14">
        <section className="flex flex-col items-center gap-3 text-center">
          <p className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-wide text-violet-700 shadow-sm shadow-violet-100">
            AI ATS SCORE
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Score &amp;{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              fix your resume
            </span>
          </h1>
          <p className="max-w-xl text-base text-gray-600">
            Upload a resume (or pick a saved profile), paste a job description, and get an
            AI-powered ATS report with keywords, gaps and concrete fixes.
          </p>
        </section>

        <section
          className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur sm:p-8"
          aria-labelledby="ats-heading"
        >
          <h2 id="ats-heading" className="sr-only">
            ATS score form
          </h2>
          <AtsScoreForm />
        </section>

        <BackendStatus />
      </div>
    </main>
  );
}
