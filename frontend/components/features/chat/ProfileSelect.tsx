"use client";

import { useEffect, useMemo } from "react";

import { useProfiles } from "@/hooks/use-profiles";

import { useChat } from "./ChatProvider";

/** Keeps the chat's profile valid and lets the user switch when they have more than one. */
export function ProfileSelect() {
  const { profileId, setProfileId } = useChat();
  const profiles = useProfiles();
  const items = useMemo(() => profiles.data ?? [], [profiles.data]);
  const known = items.some((profile) => profile.profile_id === profileId);

  useEffect(() => {
    const first = items[0];
    if (!known && first !== undefined) setProfileId(first.profile_id);
  }, [known, items, setProfileId]);

  if (items.length < 2) return null;
  return (
    <>
      <label htmlFor="chat-profile" className="sr-only">
        Profile
      </label>
      <select
        id="chat-profile"
        value={known ? (profileId ?? "") : ""}
        onChange={(event) => {
          setProfileId(event.target.value);
        }}
        className="max-w-36 truncate rounded-lg border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700"
      >
        {items.map((profile) => (
          <option key={profile.profile_id} value={profile.profile_id}>
            {profile.name}
          </option>
        ))}
      </select>
    </>
  );
}
