"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import {
  EmptyState,
  ExperienceIcon,
  ItemCard,
  ProjectsIcon,
  SectionCard,
  StringListField,
  TextField,
} from "./fields";

const emptyExperience = {
  company: "",
  title: "",
  location: "",
  start_date: "",
  end_date: "",
  is_current: false,
  bullets: [],
};

const emptyProject = {
  name: "",
  role: "",
  url: "",
  start_date: "",
  end_date: "",
  description: "",
  bullets: [],
  technologies: [],
};

const addBtn =
  "rounded-full border-dashed px-4 py-1.5 text-xs font-semibold text-violet-700 hover:border-violet-400 hover:bg-violet-50";

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
        <Button variant="secondary" className={addBtn} onClick={() => append(emptyExperience)}>
          + Add role
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No roles yet — add your work experience, internships and freelance work."
          action={
            <Button variant="secondary" className={addBtn} onClick={() => append(emptyExperience)}>
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
              onRemove={() => remove(index)}
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
                <TextField label="Company" name={`experience.${index}.company`} placeholder="e.g. Acme Corp" error={errors?.[index]?.company?.message} />
                <TextField label="Title" name={`experience.${index}.title`} placeholder="e.g. Senior Engineer" error={errors?.[index]?.title?.message} />
                <TextField label="Location" name={`experience.${index}.location`} placeholder="e.g. Berlin or Remote" />
                <div className="grid grid-cols-2 gap-3">
                  <TextField label="Start date" name={`experience.${index}.start_date`} placeholder="Mar 2021" />
                  <TextField label="End date" name={`experience.${index}.end_date`} placeholder="Present" />
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

export function ProjectsSection() {
  const { control, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "projects" });
  const errors = formState.errors.projects;

  return (
    <SectionCard
      title="Projects"
      description="Side projects, open source and portfolio work"
      icon={<ProjectsIcon />}
      defaultOpen={fields.length > 0}
      hasError={errors !== undefined}
      action={
        <Button variant="secondary" className={addBtn} onClick={() => append(emptyProject)}>
          + Add project
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No projects yet — add personal, open-source or academic projects."
          action={
            <Button variant="secondary" className={addBtn} onClick={() => append(emptyProject)}>
              + Add project
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
              onRemove={() => remove(index)}
              onMove={move}
              title={field.name || (fields.length > 1 ? `Project ${index + 1}` : undefined)}
              subtitle={field.role || undefined}
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <TextField label="Name" name={`projects.${index}.name`} placeholder="e.g. JobMatch" error={errors?.[index]?.name?.message} />
                <TextField label="Role" name={`projects.${index}.role`} placeholder="e.g. Creator, Maintainer" />
                <TextField label="URL" name={`projects.${index}.url`} placeholder="https://…" />
                <div className="grid grid-cols-2 gap-3">
                  <TextField label="Start date" name={`projects.${index}.start_date`} placeholder="Jan 2024" />
                  <TextField label="End date" name={`projects.${index}.end_date`} placeholder="Present" />
                </div>
              </div>
              <div className="mt-3">
                <TextField
                  label="Description"
                  name={`projects.${index}.description`}
                  placeholder="One or two sentences on what it does and your part in it"
                />
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <StringListField
                  control={control}
                  name={`projects.${index}.bullets`}
                  label="Bullets"
                  addLabel="Add bullet"
                  placeholder="e.g. 500+ GitHub stars"
                />
                <StringListField
                  control={control}
                  name={`projects.${index}.technologies`}
                  label="Technologies"
                  addLabel="Add technology"
                  placeholder="e.g. Next.js, Postgres"
                />
              </div>
            </ItemCard>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
