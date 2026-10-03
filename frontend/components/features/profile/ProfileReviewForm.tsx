"use client";

import { useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { toProfilePayload, type ProfileFormValues } from "@/lib/profile-schema";
import type { StructuredProfile } from "@/lib/api";

import { CertificationsSection, AwardsSection } from "./CertificationsAwards";
import { EducationSection } from "./EducationSection";
import { ExtraSectionsSection } from "./ExtraSections";
import { ExperienceSection } from "./ExperienceSection";
import { ContactSection } from "./ContactSection";
import { PreferencesSection } from "./PreferencesSection";
import { ProjectsSection } from "./ProjectsSection";
import { AiExtractedBadge, StringListField, TextField } from "./fields";
import { HeadlineIcon, SkillsIcon } from "./profile-icons";
import { SectionCard } from "./cards";
import { SaveStatus } from "./SaveStatus";

export function ProfileReviewForm({
  highlightAi,
  isSaving,
  saveError,
  savedRevisionSource,
  onSave,
}: {
  highlightAi: boolean;
  isSaving: boolean;
  saveError: string | null;
  savedRevisionSource: string | null;
  onSave: (profile: StructuredProfile) => void;
}) {
  const { control, formState, handleSubmit } = useFormContext<ProfileFormValues>();
  const aiBadge = highlightAi ? <AiExtractedBadge /> : undefined;
  const errors = formState.errors;

  const submit = handleSubmit((values) => {
    onSave(toProfilePayload(values));
  });

  return (
    <form
      onSubmit={(event) => {
        void submit(event);
      }}
      className="flex flex-col gap-5"
      noValidate
    >
      <ContactSection aiBadge={aiBadge} />

      <SectionCard
        title="Headline & summary"
        description="Your elevator pitch — what you do and what you're looking for"
        icon={<HeadlineIcon />}
        badge={aiBadge}
        hasError={errors.headline !== undefined || errors.summary !== undefined}
      >
        <div className="flex flex-col gap-4">
          <TextField
            label="Headline"
            name="headline"
            placeholder="Senior Android Developer"
            error={errors.headline?.message}
            badge={aiBadge}
          />
          <TextField
            label="Summary"
            name="summary"
            placeholder="A short paragraph summarising your experience and strengths…"
            badge={aiBadge}
          />
        </div>
      </SectionCard>

      <SectionCard
        title="Skills"
        description="Your strongest and most relevant skills — order matters"
        icon={<SkillsIcon />}
        badge={aiBadge}
        hasError={errors.skills !== undefined}
      >
        <StringListField
          control={control}
          name="skills"
          label="Skills"
          addLabel="Add skill"
          placeholder="e.g. Kotlin, React, SQL"
        />
      </SectionCard>

      <ExperienceSection />
      <ProjectsSection />
      <EducationSection />
      <CertificationsSection />
      <AwardsSection />
      <ExtraSectionsSection />

      <PreferencesSection aiBadge={aiBadge} />

      <div className="sticky bottom-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-violet-100 bg-white/95 p-4 shadow-xl shadow-violet-100/60 backdrop-blur">
        <SaveStatus
          isSaving={isSaving}
          error={saveError}
          savedRevisionSource={savedRevisionSource}
        />
        {errors.root?.message && (
          <p role="alert" className="text-sm text-red-600">
            {errors.root.message}
          </p>
        )}
        <Button
          type="submit"
          disabled={isSaving}
          className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 py-2.5 font-semibold shadow-lg shadow-violet-200 hover:from-violet-700 hover:to-fuchsia-700"
        >
          {isSaving ? "Saving…" : "Save profile"}
        </Button>
      </div>
    </form>
  );
}
