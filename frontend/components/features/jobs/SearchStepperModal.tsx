"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { FormProvider, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useStartJobSearch } from "@/hooks/use-job-search";
import { useProfile } from "@/hooks/use-profiles";
import { type ProfileSummary, type SourceInfo } from "@/lib/api";

import { SearchRunErrors } from "./SearchRunErrors";
import { StepIndicator } from "./StepIndicator";
import { LAST_STEP, STEP_FIELDS } from "./search-steps";
import { useSeedSearchForm } from "./use-seed-search-form";
import { SearchStepContent } from "./SearchStepContent";
import {
  emptySearchFormValues,
  missingFieldMessage,
  makeSearchFormSchema,
  toSearchRequest,
  type SearchFormValues,
} from "./search-form-schema";

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
  const start = useStartJobSearch();
  const structured = profileQuery.data?.structured_profile ?? null;
  const schema = useMemo(() => makeSearchFormSchema(selectedSource), [selectedSource]);

  const form = useForm<SearchFormValues>({
    resolver: standardSchemaResolver(schema),
    defaultValues: emptySearchFormValues(),
    mode: "onBlur",
  });

  // Reset the wizard whenever it opens: adjust state during render when the
  // `open` prop flips (the render-phase adjustment pattern).
  const [wasOpen, setWasOpen] = useState(open);
  if (open && !wasOpen) {
    setWasOpen(true);
    setStep(1);
    setSourceName("");
  } else if (!open && wasOpen) {
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

  useSeedSearchForm({
    form,
    structured,
    profile: profileQuery.data,
    sourceName,
    selectedSource,
    activeProfileId,
  });

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
      form.setError("root", { message: missingFieldMessage(missing[0], selectedSource) });
      return;
    }
    form.clearErrors("root");
    start.mutate(payload, {
      onSuccess: (data) => {
        onSearchStarted(data.search_id);
      },
    });
  });

  // Submissions only come from the review step's button in principle, but
  // implicit submit events (Enter in any input at any step) land on the form
  // too. They advance the wizard instead of ever starting a run early.
  const onFormSubmit = (event: React.SubmitEvent<HTMLFormElement>) => {
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
          <StepIndicator step={step} />

          <SearchStepContent
            step={step}
            profiles={{
              list: profilesList,
              pending: profilesPending,
              error: profilesError,
              activeId: activeProfileId,
              onSelect: onSelectProfile,
            }}
            sources={sources}
            sourceName={sourceName}
            onSelectSource={setSourceName}
            selectedSource={selectedSource}
            profile={profileQuery.data}
            currency={currency}
          />

          <div className="flex items-center justify-between gap-3 border-t border-gray-100 pt-4">
            <Button type="button" variant="secondary" disabled={step === 1} onClick={goingBack}>
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
          <SearchRunErrors
            error={start.isError ? start.error : null}
            onSearchStarted={onSearchStarted}
            onClose={() => {
              onOpenChange(false);
            }}
          />
        </form>
      </FormProvider>
    </Modal>
  );
}
