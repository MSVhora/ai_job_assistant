import { BackendStatus } from "@/components/features/BackendStatus";
import { ProfilesSection } from "@/components/features/ProfilesSection";
import { ResumeList } from "@/components/features/ResumeList";
import { ResumeUploadForm } from "@/components/features/ResumeUploadForm";
import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 p-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          AI Job Assistant
        </h1>
        <p className="max-w-md text-gray-600 dark:text-gray-400">
          Self-hosted, bring-your-own-key job matching. Upload a resume, save it as one or more
          profiles, and match each track separately.
        </p>
      </div>
      <div className="flex justify-center">
        <ResumeUploadForm />
      </div>
      <ProfilesSection />
      <ResumeList />
      <p className="text-center text-sm text-gray-600 dark:text-gray-400">
        Want to review or merge a draft?{" "}
        <Link
          href="/profile"
          className="font-medium text-blue-700 underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:text-blue-400"
        >
          Go to your profiles
        </Link>
      </p>
      <BackendStatus />
    </main>
  );
}
