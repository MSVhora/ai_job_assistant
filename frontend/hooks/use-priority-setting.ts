"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { useProfile, useUpdatePreferences } from "@/hooks/use-profiles";

const COMMIT_DEBOUNCE_MS = 250;

export type PrioritySetting = ReturnType<typeof usePrioritySetting>;

export function usePrioritySetting(profileId: string | null) {
  const profile = useProfile(profileId);
  const updatePreferences = useUpdatePreferences();
  const [override, setOverride] = useState<number | undefined>(undefined);
  const [committed, setCommitted] = useState<number | undefined>(undefined);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stored = profile.data?.preferences?.priority;
  const value = override ?? stored;

  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
    },
    [],
  );

  const change = (next: number) => {
    setOverride(next);
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setCommitted(next);
      if (profileId === null) return;
      updatePreferences.mutate(
        { profileId, payload: { priority: next } },
        {
          onError: () => {
            toast.error("Couldn't save the preference — ranking reflects this session only.", {
              id: "preferences-save-failed",
            });
          },
        },
      );
    }, COMMIT_DEBOUNCE_MS);
  };

  return { value, listValue: committed, change, disabled: profile.isPending };
}
