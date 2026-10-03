"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { useIngestResume } from "@/hooks/use-evidence-sources";
import { useProfiles } from "@/hooks/use-profiles";

export function ResumeIngest() {
  const profiles = useProfiles();
  const ingest = useIngestResume();
  const [profileId, setProfileId] = useState("");
  const chosen = profileId !== "" ? profileId : (profiles.data?.[0]?.profile_id ?? "");

  if (profiles.isSuccess && profiles.data.length === 0) {
    return (
      <p className="text-sm text-gray-600">
        Create a profile from your resume first, then its bullets can be used as evidence.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Field
        label="Profile"
        htmlFor="ingest-profile"
        hint="Every experience and project bullet of this profile becomes an evidence item."
      >
        <Select
          id="ingest-profile"
          value={chosen}
          disabled={!profiles.isSuccess}
          onChange={(event) => {
            setProfileId(event.target.value);
          }}
        >
          {(profiles.data ?? []).map((profile) => (
            <option key={profile.profile_id} value={profile.profile_id}>
              {profile.name}
            </option>
          ))}
        </Select>
      </Field>
      <div>
        <Button
          variant="secondary"
          disabled={chosen === "" || ingest.isPending}
          onClick={() => {
            ingest.mutate(chosen, {
              onSuccess: (result) => {
                toast.success(
                  `Resume entries: ${result.created} new, ${result.unchanged} unchanged, ${result.excluded} removed`,
                );
              },
            });
          }}
        >
          Ingest resume entries
        </Button>
      </div>
    </div>
  );
}
