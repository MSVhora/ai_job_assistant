import type { ProfileResponse, ProfileSummary, SourceInfo } from "@/lib/api";

import { DetailsStep } from "./DetailsStep";
import { ProfileStep, SourceStep } from "./ProfileSourceSteps";
import { ReviewSummary } from "./ReviewSummary";

export function SearchStepContent({
  step,
  profiles,
  sources,
  sourceName,
  onSelectSource,
  selectedSource,
  profile,
  currency,
}: {
  step: number;
  profiles: {
    list: ProfileSummary[];
    pending: boolean;
    error: boolean;
    activeId: string | null;
    onSelect: (profileId: string) => void;
  };
  sources: SourceInfo[];
  sourceName: string;
  onSelectSource: (sourceName: string) => void;
  selectedSource: SourceInfo | null;
  profile: ProfileResponse | undefined;
  currency: string | null;
}) {
  return (
    <>
      {step === 1 && (
        <ProfileStep
          profiles={profiles.list}
          activeProfileId={profiles.activeId}
          profilesPending={profiles.pending}
          profilesError={profiles.error}
          onSelectProfile={profiles.onSelect}
        />
      )}
      {step === 2 && (
        <SourceStep sources={sources} selectedSourceId={sourceName} onSelect={onSelectSource} />
      )}
      {step === 3 && selectedSource !== null && (
        <DetailsStep
          source={selectedSource}
          profileId={profiles.activeId}
          structuredProfile={profile?.structured_profile ?? null}
          storedQueries={profile?.search_queries ?? null}
          updatedAt={profile?.updated_at}
          currency={currency}
        />
      )}
      {step === 4 && selectedSource !== null && (
        <div aria-label="Step 4: review" className="flex flex-col gap-3">
          <ReviewSummary
            source={selectedSource}
            profileName={profile?.name ?? null}
            currency={currency}
          />
        </div>
      )}
    </>
  );
}
