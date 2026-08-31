import { BackendStatus } from "@/components/features/BackendStatus";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">AI Job Assistant</h1>
        <p className="max-w-md text-gray-600">
          Self-hosted, bring-your-own-key job matching. Upload a resume, review your profile, get
          ranked matches.
        </p>
      </div>
      <BackendStatus />
    </main>
  );
}
