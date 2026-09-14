"use client";

import { RunBanner } from "./RunBanner";

export function RunBanners({
  searchIds,
  profileId,
  onDismiss,
}: {
  searchIds: string[];
  profileId: string | null;
  onDismiss: (searchId: string) => void;
}) {
  return (
    <>
      {searchIds.map((searchId) => (
        <RunBanner
          key={searchId}
          searchId={searchId}
          profileId={profileId}
          onDismiss={() => onDismiss(searchId)}
        />
      ))}
    </>
  );
}
