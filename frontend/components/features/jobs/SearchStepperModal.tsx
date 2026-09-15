"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { FormProvider, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useStartJobSearch } from "@/hooks/use-job-search";
import { useProfile } from "@/hooks/use-profiles";
import type { ProfileSummary, SourceInfo } from "@/lib/api";

import { DetailsStep, ProfileStep, ReviewSummary, SourceStep } from "./SearchSteps";
import {
  emptyQueryFields,
  makeSearchFormSchema,
  optionsFromStored,
  seedSpec,
  toSearchRequest,
  type SearchFormValues,
} from "./search-form-schema";

const STEP_LABELS = ["Profile", "Source", "Details", "Review"] as const;
const LAST_STEP = 4;

const STEP_FIELDS: (keyof SearchFormValues | string)[][] = [
  [],
  ["source"],
  [
    "query.title",
    "query.skills",
    "query.exclude",
    "location",
    "country",
    "minSalary",
    "maxSalary",
    "posted_within",
    "results_wanted",
  ],
  [],
];

function StartSearchButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-haspopup="dialog"
      className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-violet-300 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
    >
      Start search
      <span className="block text-[11px] font-medium text-violet-100">
        One profile · one source per run
      </span>
    </button>
  );
}

export function SearchStepperModal({
  open,
  onOpenChange,
  profilesPending,
  profilesError,
  profilesList,
  activeProfileId,
  onSelectProfile,
  sources,
  onSearchStarted,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profilesPending: boolean;
  profilesError: boolean;
  profilesList: ProfileSummary[];
  activeProfileId: string | null;
  onSelectProfile: (profileId: string) => void;
  sources: SourceInfo[];
  onSearchStarted: (searchId: string) => void;
}) {
  const [step, setStep] = useState(1);
  const step4AtRef = useRef<number | null>(null);
  const [sourceName, setSourceName] = useState("");
  const selectedSource = sources.find((source) => source.name === sourceName) ?? null;
  const profileQuery = useProfile(activeProfileId);
  const profileName = profileQuery.data?.name ?? null;
  const start = useStartJobSearch();
  const structured = profileQuery.data?.structured_profile ?? null;
  const schema = useMemo(() => makeSearchFormSchema(selectedSource), [selectedSource]);

  const form = useForm<SearchFormValues>({
    resolver: standardSchemaResolver(schema),
    defaultValues: {
      query: emptyQueryFields(),
      source: "",
      location: "",
      country: "",
      minSalary: "",
      maxSalary: "",
      posted_within: "any",
      results_wanted: 50,
    },
    mode: "onBlur",
  });

  // Reset the wizard whenever it opens: adjust state during render when the
  // `open` prop flips (the render-phase adjustment pattern).
  const [wasOpen, setWasOpen] = useState(open);
  if (open === true && wasOpen === false) {
    setWasOpen(true);
    setStep(1);
    setSourceName("");
  } else if (open === false && wasOpen === true) {
    setWasOpen(false);
  }

  // A fresh open must not inherit a step-enter timestamp from the last one.
  useEffect(() => {
    if (!open) return;
    step4AtRef.current = null;
  }, [open]);


  useEffect(() => {
    form.setValue("source", sourceName, { shouldValidate: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceName]);

  // Re-seed prefilled values on profile switch, source switch, and after a
  // regenerate refreshes the stored per-source queries.
  useEffect(() => {
    if (structured === null) {
      return;
    }
    const preferences = structured.preferences;
    const stored = profileQuery.data?.search_queries?.queries[sourceName];
    const seeded = seedSpec(structured);
    form.reset({
      query: {
        title: stored?.title ?? seeded.title,
        skills: (stored?.skills ?? seeded.skills).join(", "),
        exclude: (stored?.exclude ?? []).join(", "),
        options: optionsFromStored(stored?.options, selectedSource),
      },
      source: sourceName,
      location: preferences?.target_location || structured.contact.location || "",
      country: structured.contact.country || "",
      minSalary:
        preferences?.salary_min !== undefined && preferences?.salary_min !== null
          ? String(preferences.salary_min)
          : "",
      maxSalary:
        preferences?.salary_max !== undefined && preferences?.salary_max !== null
          ? String(preferences.salary_max)
          : "",
      posted_within: "any" as const,
      results_wanted: 50,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeProfileId,
    sourceName,
    profileQuery.data?.updated_at,
    profileQuery.data?.search_queries?.generated_at,
  ]);

  const advance = async () => {
    const fields = STEP_FIELDS[step - 1];
    if (step === 1) {
      if (activeProfileId === null) {
        form.setError("root", { message: "Select a profile before continuing." });
        return;
      }
      form.clearErrors("root");
      setStep(2);
      return;
    }
    const ok = await form.trigger(fields as never, { shouldFocus: true });
    if (ok) {
      form.clearErrors("root");
      if (step + 1 === LAST_STEP) {
        step4AtRef.current = Date.now();
      }
      setStep((current) => Math.min(current + 1, LAST_STEP));
    }
  };

  const submit = form.handleSubmit((values) => {
    const { payload, missing } = toSearchRequest(
      values,
      selectedSource,
      structured?.preferences?.currency ?? null,
      activeProfileId,
    );
    if (missing.length > 0) {
      form.setError("root", {
        message:
          missing[0] === "profile"
            ? "Select a profile before starting a search (every run is scoped to one)."
            : missing[0] === "source"
              ? "Pick the source to search."
              : `Add a title, skills, or advanced filters for ${selectedSource?.name ?? "this source"}.`,
      });
      return;
    }
    form.clearErrors("root");
    start.mutate(payload, {
      onSuccess: (data) => onSearchStarted(data.search_id),
    });
  });

  // Submissions only come from the review step's button in principle, but
  // implicit submit events (Enter in any input at any step) land on the form
  // too. They advance the wizard instead of ever starting a run early.
  const onFormSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    // A submit must come from an explicit press on the review step AFTER it
    // rendered: the tail end of the pointer gesture that advanced the wizard
    // (pointer-up landing on the submit button that mounts in the Next
    // button's slot) is ignored.
    const fresh = step4AtRef.current !== null && Date.now() - step4AtRef.current < 400;
    if (step === LAST_STEP && fresh) {
      event.preventDefault();
      return;
    }
    event.preventDefault();
    if (step < LAST_STEP) {
      void advance();
      return;
    }
    void submit();
  };

  const currency = structured?.preferences?.currency ?? null;
  const goingBack = () => {
    setStep((current) => Math.max(current - 1, 1));
  };


  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Start a search"
      description="One profile and one source per run — you can start other searches while this one runs."
    >
      <FormProvider {...form}>
        <form onSubmit={onFormSubmit} className="flex flex-col gap-5" noValidate>
          <ol aria-label="Steps" className="flex flex-wrap items-center gap-2 text-xs">
            {STEP_LABELS.map((label, index) => {
              const number = index + 1;
              const current = number === step;
              return (
                <li
                  key={label}
                  aria-current={current ? "step" : undefined}
                  className={`flex items-center gap-1.5 rounded-full border px-3 py-1 font-semibold ${
                    current
                      ? "border-violet-400 bg-violet-50 text-violet-800"
                      : number < step
                        ? "border-gray-200 bg-gray-50 text-gray-600"
                        : "border-dashed border-gray-200 text-gray-400"
                  }`}
                >
                  <span>{number}.</span>
                  <span>{label}</span>
                </li>
              );
            })}
          </ol>

          {step === 1 && (
            <ProfileStep
              profiles={profilesList}
              activeProfileId={activeProfileId}
              profilesPending={profilesPending}
              profilesError={profilesError}
              onSelectProfile={onSelectProfile}
            />
          )}
          {step === 2 && (
            <SourceStep
              sources={sources}
              selectedSourceId={sourceName}
              onSelect={setSourceName}
            />
          )}
          {step === 3 && selectedSource !== null && (
            <DetailsStep
              source={selectedSource}
              profileId={activeProfileId}
              structuredProfile={structured}
              storedQueries={profileQuery.data?.search_queries ?? null}
              updatedAt={profileQuery.data?.updated_at}
              currency={currency}
            />
          )}
          {step === 4 && selectedSource !== null && (
            <div aria-label="Step 4: review" className="flex flex-col gap-3">
              <ReviewSummary
                source={selectedSource}
                profileName={profileName}
                currency={currency}
              />
            </div>
          )}

          <div className="flex items-center justify-between gap-3 border-t border-gray-100 pt-4">
            <Button
              type="button"
              variant="secondary"
              disabled={step === 1}
              onClick={goingBack}
            >
              Back
            </Button>
            {step < LAST_STEP ? (
              <Button
                type="button"
                disabled={step === 1 && activeProfileId === null}
                onClick={() => void advance()}
              >
                {step === 4 ? "Start search" : "Next"}
              </Button>
            ) : (
              <Button type="submit" disabled={start.isPending}>
                {start.isPending ? "Starting run…" : "Start search"}
              </Button>
            )}
          </div>
          {form.formState.errors.root && (
            <p role="alert" className="text-xs text-red-600">
              {form.formState.errors.root.message}
            </p>
          )}
          {start.isError && (
            <p role="alert" className="text-xs text-red-600">
              {start.error.message}
            </p>
          )}
        </form>
      </FormProvider>
    </Modal>
  );
}

export { StartSearchButton };
