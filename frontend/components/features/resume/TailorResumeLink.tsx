import Link from "next/link";

import { resumeBuilderHref } from "@/lib/resume-view";

export function TailorResumeLink({
  profileId,
  matchId,
}: {
  profileId: string | null;
  matchId: string;
}) {
  return (
    <Link
      href={resumeBuilderHref(profileId, matchId)}
      className="inline-flex items-center rounded-xl border border-violet-300 bg-white px-4 py-2 text-xs font-bold text-violet-700 transition-colors hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
    >
      Tailor resume
    </Link>
  );
}
