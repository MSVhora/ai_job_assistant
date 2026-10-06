import { OptionCard } from "@/components/features/get-started/OptionCard";
import { OPTIONS } from "@/components/features/get-started/options";
import { SparkleIcon } from "@/components/features/get-started/icons";

export const metadata = {
  title: "Get started",
  description: "Choose where to start: job search, profiles, API keys and more.",
};

export default function GetStartedPage() {
  return (
    <main className="relative flex min-h-screen w-full flex-col overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute inset-x-0 top-0 h-[420px] bg-gradient-to-b from-violet-50 via-fuchsia-50/50 to-transparent" />
        <div className="absolute top-10 -left-24 h-72 w-72 rounded-full bg-violet-300/40 blur-3xl" />
        <div className="absolute top-32 -right-24 h-72 w-72 rounded-full bg-fuchsia-300/30 blur-3xl" />
      </div>

      <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-3 px-6 pt-16 pb-16 text-center">
        <p className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-wide text-violet-700 shadow-sm shadow-violet-100">
          <SparkleIcon className="h-3.5 w-3.5" />
          Choose your path
        </p>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          What would you like to do{" "}
          <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
            today?
          </span>
        </h1>
        <p className="max-w-xl text-base text-gray-600 sm:text-lg">
          Pick a starting point — every path keeps you in control while AI does the heavy lifting.
        </p>

        <div className="mt-12 grid w-full gap-6 pt-3 sm:grid-cols-2 lg:grid-cols-3">
          {OPTIONS.map((option) => (
            <OptionCard key={option.eyebrow} option={option} />
          ))}
        </div>
      </div>
    </main>
  );
}
