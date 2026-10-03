"use client";

import { MatchFilterPanel } from "@/components/features/jobs/MatchFilterPanel";
import { ProfileSelector } from "@/components/features/jobs/ProfileSelector";
import { RebuildBanner } from "@/components/features/jobs/RebuildBanner";
import { StartSearchButton } from "@/components/features/jobs/StartSearchButton";
import type { MatchFilterValues } from "@/hooks/use-matches";
import type { usePrioritySetting } from "@/hooks/use-priority-setting";
import type { ProfileSummary } from "@/lib/api";

function FunnelIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <path d="M3 5h18l-7 8v5.5L10 20v-7z" />
    </svg>
  );
}

export function JobsFilterSidebar({
  profiles,
  filters,
  onChangeFilters,
  priority,
  onStartSearch,
}: {
  profiles: {
    list: ProfileSummary[];
    activeId: string | null;
    disabled: boolean;
    onSelect: (profileId: string) => void;
  };
  filters: MatchFilterValues;
  onChangeFilters: (filters: MatchFilterValues) => void;
  priority: ReturnType<typeof usePrioritySetting>;
  onStartSearch: () => void;
}) {
  return (
    <aside
      aria-label="Job list filters"
      className="flex flex-col self-start overflow-hidden rounded-3xl border border-violet-100 bg-white/80 shadow-xl shadow-violet-100/60 backdrop-blur lg:sticky lg:top-4 lg:h-[calc(100vh-13rem)]"
    >
      <div className="flex shrink-0 items-center gap-2.5 border-b border-gray-100 px-5 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
          <FunnelIcon />
        </span>
        <div>
          <h2 className="text-base font-bold tracking-tight text-gray-900">Filters</h2>
          <p className="text-xs text-gray-500">Narrow the ranked list</p>
        </div>
      </div>
      <div className="scrollbar-hidden flex min-h-0 flex-1 grow flex-col gap-5 overflow-y-auto p-5">
        <section
          className="rounded-2xl border border-violet-100 bg-violet-50/40 p-3"
          aria-label="Profile scope"
        >
          <ProfileSelector
            profiles={profiles.list}
            activeProfileId={profiles.activeId}
            disabled={profiles.disabled}
            onSelect={profiles.onSelect}
            id="filter-profile"
            hint="Every search run and the match list below are scoped to this profile."
          />
        </section>
        <MatchFilterPanel filters={filters} onChange={onChangeFilters} priority={priority} />
      </div>
      <div className="flex shrink-0 flex-col gap-2 border-t border-gray-100 p-3">
        <RebuildBanner profileId={profiles.activeId} />
        <StartSearchButton onClick={onStartSearch} />
      </div>
    </aside>
  );
}
