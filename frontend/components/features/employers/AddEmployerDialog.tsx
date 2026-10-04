"use client";

import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { useQueryClient } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { useAddEmployer } from "@/hooks/use-employers";
import { useProfiles } from "@/hooks/use-profiles";
import type { EmployerOption, ExperienceCreate } from "@/lib/api";
import { findOptionForRef, optionKey } from "@/lib/employer-options";

const schema = z.object({
  profile_id: z.string().min(1, "Choose a profile"),
  company: z
    .string()
    .trim()
    .min(1, "Enter the company name")
    .max(200, "Keep it under 200 characters"),
  title: z.string().max(200),
  start_date: z.string().max(50),
  end_date: z.string().max(50),
  is_current: z.boolean(),
});

type Values = z.infer<typeof schema>;

function payloadOf(values: Values): ExperienceCreate {
  const payload: ExperienceCreate = {
    company: values.company.trim(),
    is_current: values.is_current,
  };
  if (values.title.trim() !== "") payload.title = values.title.trim();
  if (values.start_date.trim() !== "") payload.start_date = values.start_date.trim();
  if (values.end_date.trim() !== "" && !values.is_current)
    payload.end_date = values.end_date.trim();
  return payload;
}

/** Adds a role (so an employer) to a profile: resumes can only show companies the profile has. */
export function AddEmployerDialog({
  open,
  onClose,
  onAdded,
}: {
  open: boolean;
  onClose: () => void;
  onAdded?: ((key: string) => void) | undefined;
}) {
  const profiles = useProfiles();
  const add = useAddEmployer();
  const queryClient = useQueryClient();
  const list = [...(profiles.data ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors },
  } = useForm<Values>({
    resolver: standardSchemaResolver(schema),
    values: {
      profile_id: list[0]?.profile_id ?? "",
      company: "",
      title: "",
      start_date: "",
      end_date: "",
      is_current: false,
    },
  });
  const current = useWatch({ control, name: "is_current" });

  const submit = handleSubmit((values) => {
    add.mutate(
      { profileId: values.profile_id, payload: payloadOf(values) },
      {
        onSuccess: () => {
          const options = queryClient.getQueryData<EmployerOption[]>(["evidence-employers"]) ?? [];
          const option = findOptionForRef(options, { company: values.company.trim() });
          const profile = list.find((item) => item.profile_id === values.profile_id);
          toast.success(`${values.company.trim()} added to ${profile?.name ?? "the profile"}`);
          reset();
          onClose();
          if (option !== undefined) onAdded?.(optionKey(option));
        },
      },
    );
  });

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title="Add an employer"
      description="For a company that is not on your resume. It is added to a profile as a role, so resumes and checks can use it."
    >
      <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-3" noValidate>
        <Field label="Company" htmlFor="employer-company" error={errors.company?.message}>
          <Input
            id="employer-company"
            aria-invalid={errors.company !== undefined}
            {...register("company")}
          />
        </Field>
        <Field label="Role (optional)" htmlFor="employer-title">
          <Input id="employer-title" {...register("title")} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Start (optional)" htmlFor="employer-start" hint="For example Jan 2022.">
            <Input id="employer-start" {...register("start_date")} />
          </Field>
          <Field label="End (optional)" htmlFor="employer-end">
            <Input id="employer-end" disabled={current} {...register("end_date")} />
          </Field>
        </div>
        <Checkbox label="I work here now" {...register("is_current")} />
        {list.length > 1 && (
          <Field
            label="Add to profile"
            htmlFor="employer-profile"
            error={errors.profile_id?.message}
          >
            <Select id="employer-profile" {...register("profile_id")}>
              {list.map((profile) => (
                <option key={profile.profile_id} value={profile.profile_id}>
                  {profile.name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <p className="text-xs text-gray-600">
          This adds a role to{" "}
          {list.length === 1 ? `the profile “${list[0]?.name ?? ""}”` : "the chosen profile"} and
          saves it like any profile edit, which re-scores your job matches. Without dates the
          employer cannot be matched to when you did the work.
        </p>
        {add.isError && (
          <p role="alert" className="text-sm text-red-700">
            {add.error.message}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={add.isPending || list.length === 0}>
            {add.isPending ? "Adding…" : "Add employer"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
