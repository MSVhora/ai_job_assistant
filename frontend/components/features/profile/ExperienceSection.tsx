"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import { addButtonClass as addBtn, EmptyState, ItemCard, SectionCard } from "./cards";
import { ExperienceIcon } from "./profile-icons";
import { StringListField, TextField } from "./fields";

const emptyExperience = {
  company: "",
  title: "",
  location: "",
  start_date: "",
  end_date: "",
  is_current: false,
  bullets: [],
};

export function ExperienceSection() {
  const { control, register, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "experience" });
  const errors = formState.errors.experience;

  return (
    <SectionCard
      title="Experience"
      description="Roles you've held — most recent first"
      icon={<ExperienceIcon />}
      defaultOpen={fields.length > 0}
      hasError={errors !== undefined}
      action={
        <Button
          variant="secondary"
          className={addBtn}
          onClick={() => {
            append(emptyExperience);
          }}
        >
          + Add role
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No roles yet — add your work experience, internships and freelance work."
          action={
            <Button
              variant="secondary"
              className={addBtn}
              onClick={() => {
                append(emptyExperience);
              }}
            >
              + Add role
            </Button>
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          {fields.map((field, index) => (
            <ItemCard
              key={field.id}
              index={index}
              count={fields.length}
              onRemove={() => {
                remove(index);
              }}
              onMove={move}
              title={
                field.title || field.company
                  ? [field.title, field.company].filter(Boolean).join(" @ ")
                  : fields.length > 1
                    ? `Role ${index + 1}`
                    : undefined
              }
              subtitle={
                field.start_date || field.end_date
                  ? [field.start_date, field.end_date].filter(Boolean).join(" — ")
                  : undefined
              }
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <TextField
                  label="Company"
                  name={`experience.${index}.company`}
                  placeholder="e.g. Acme Corp"
                  error={errors?.[index]?.company?.message}
                />
                <TextField
                  label="Title"
                  name={`experience.${index}.title`}
                  placeholder="e.g. Senior Engineer"
                  error={errors?.[index]?.title?.message}
                />
                <TextField
                  label="Location"
                  name={`experience.${index}.location`}
                  placeholder="e.g. Berlin or Remote"
                />
                <div className="grid grid-cols-2 gap-3">
                  <TextField
                    label="Start date"
                    name={`experience.${index}.start_date`}
                    placeholder="Mar 2021"
                  />
                  <TextField
                    label="End date"
                    name={`experience.${index}.end_date`}
                    placeholder="Present"
                  />
                </div>
              </div>
              <label className="mt-3 flex w-fit items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 accent-violet-600"
                  {...register(`experience.${index}.is_current`)}
                />
                I currently work here
              </label>
              <div className="mt-3">
                <StringListField
                  control={control}
                  name={`experience.${index}.bullets`}
                  label="Bullets"
                  addLabel="Add bullet"
                  placeholder="e.g. Led migration of 3 services to Kotlin"
                />
              </div>
            </ItemCard>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
