import { BackendStatus } from "@/components/features/BackendStatus";
import { ResumeUploadForm } from "@/components/features/ResumeUploadForm";
import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          AI Job Assistant
        </h1>
        <p className="max-w-md text-gray-600 dark:text-gray-400">
          Self-hosted, bring-your-own-key job matching. Upload a resume, review your profile, get
          ranked matches.
        </p>
      </div>
      <ResumeUploadForm />
      <p className="text-sm text-gray-600 dark:text-gray-400">
        Already saved a profile?{" "}
        <Link
          href="/profile"
          className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Review it here
        </Link>
      </p>
      <BackendStatus />
    </main>
  );
}
