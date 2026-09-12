import Link from "next/link";

import {
  AtsScoreMock,
  MatchesMock,
  ProfileMock,
  ResumeBuilderMock,
} from "@/components/features/FeatureMocks";
import { Reveal } from "@/components/features/Reveal";

const FEATURES = [
  {
    eyebrow: "Build",
    title: "AI Resume Builder",
    description:
      "Generate tailored, ATS-ready resumes for every application, based on your skills and experience.",
    Mock: ResumeBuilderMock,
  },
  {
    eyebrow: "Optimize",
    title: "AI ATS Score Checker",
    description:
      "See how applicant tracking systems score your resume — with concrete fixes that raise your score.",
    Mock: AtsScoreMock,
  },
  {
    eyebrow: "Profile",
    title: "AI Job Profile Creation",
    description:
      "Upload a resume once and AI drafts a structured profile. You review and approve every field.",
    Mock: ProfileMock,
  },
  {
    eyebrow: "Match",
    title: "Strong-Match Openings in Minutes",
    description:
      "Ingestion runs across all your job sources and ranks the strongest openings in minutes — with explanations.",
    Mock: MatchesMock,
  },
] as const;

function ArrowIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
    >
      <path
        fillRule="evenodd"
        d="M3 10a1 1 0 011-1h10.6l-3.3-3.3a1 1 0 111.4-1.4l5 5a1 1 0 010 1.4l-5 5a1 1 0 11-1.4-1.4L14.6 11H4a1 1 0 01-1-1z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function FeaturesSection() {
  return (
    <section className="bg-gradient-to-b from-transparent via-violet-100/40 to-transparent py-20 text-gray-900">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="flex flex-col items-center gap-4 text-center">
          <p className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-4 py-1.5 text-xs font-semibold tracking-wide text-violet-700 shadow-sm shadow-violet-100">
            Features
          </p>
          <h2 className="max-w-3xl text-3xl font-bold tracking-tight sm:text-5xl">
            Everything you need to go from resume to role —{" "}
            <span className="bg-gradient-to-r from-violet-600 via-purple-600 to-fuchsia-600 bg-clip-text text-transparent">
              powered by AI
            </span>
          </h2>
          <p className="max-w-2xl text-base text-gray-600 sm:text-lg">
            Four AI helpers work together so you spend less time searching and more time
            interviewing.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-6 lg:grid-cols-2">
          {FEATURES.map((feature, index) => (
            <Reveal key={feature.title}>
              <article
                className={`group flex h-full flex-col rounded-3xl border p-8 shadow-xl transition-shadow hover:shadow-2xl ${
                  index % 2 === 0
                    ? "border-violet-200/70 bg-gradient-to-br from-white via-violet-50/80 to-fuchsia-50/60 shadow-violet-200/50 hover:shadow-violet-300/60"
                    : "border-fuchsia-200/70 bg-gradient-to-br from-white via-fuchsia-50/80 to-violet-50/60 shadow-fuchsia-200/50 hover:shadow-fuchsia-300/60"
                }`}
              >
                <p className="text-xs font-bold uppercase tracking-widest text-violet-600">
                  {feature.eyebrow}
                </p>
                <h3 className="mt-2 text-2xl font-bold tracking-tight">{feature.title}</h3>
                <p className="mt-2 text-base leading-relaxed text-gray-600">
                  {feature.description}
                </p>
                <div className="mt-4">
                  <Link
                    href="/get-started"
                    className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
                  >
                    Start now
                    <ArrowIcon />
                  </Link>
                </div>
                <div className="mt-6 flex-1">
                  <feature.Mock />
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
