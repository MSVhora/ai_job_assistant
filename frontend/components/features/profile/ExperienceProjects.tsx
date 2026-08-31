"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import { ItemCard, SectionCard, StringListField, TextField } from "./fields";

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

export function ExperienceSection() {
  const { control, register, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "experience" });
  const errors = formState.errors.experience;

  return (
    <SectionCard
      title="Experience"
      action={<Button variant="secondary" onClick={() => append(emptyExperience)}>Add role</Button>}
    >
      {fields.length === 0 && <p className="text-sm text-gray-500">No roles yet.</p>}
      <div className="flex flex-col gap-4">
        {fields.map((field, index) => (
          <ItemCard
            key={field.id}
            index={index}
            count={fields.length}
            onRemove={() => remove(index)}
            onMove={move}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label="Company" name={`experience.${index}.company`} error={errors?.[index]?.company?.message} />
              <TextField label="Title" name={`experience.${index}.title`} error={errors?.[index]?.title?.message} />
              <TextField label="Location" name={`experience.${index}.location`} />
              <div className="grid grid-cols-2 gap-3">
                <TextField label="Start date" name={`experience.${index}.start_date`} placeholder="Mar 2021" />
                <TextField label="End date" name={`experience.${index}.end_date`} placeholder="Present" />
              </div>
            </div>
            <label className="mt-3 flex items-center gap-2 text-sm text-gray-800">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300"
                {...register(`experience.${index}.is_current`)}
              />
              Current role
            </label>
            <div className="mt-3">
              <StringListField
                control={control}
                name={`experience.${index}.bullets`}
                label="Bullets"
                addLabel="Add bullet"
              />
            </div>
          </ItemCard>
        ))}
      </div>
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
      action={<Button variant="secondary" onClick={() => append(emptyProject)}>Add project</Button>}
    >
      {fields.length === 0 && <p className="text-sm text-gray-500">No projects yet.</p>}
      <div className="flex flex-col gap-4">
        {fields.map((field, index) => (
          <ItemCard
            key={field.id}
            index={index}
            count={fields.length}
            onRemove={() => remove(index)}
            onMove={move}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label="Name" name={`projects.${index}.name`} error={errors?.[index]?.name?.message} />
              <TextField label="Role" name={`projects.${index}.role`} />
              <TextField label="URL" name={`projects.${index}.url`} />
              <div className="grid grid-cols-2 gap-3">
                <TextField label="Start date" name={`projects.${index}.start_date`} />
                <TextField label="End date" name={`projects.${index}.end_date`} />
              </div>
            </div>
            <div className="mt-3">
              <TextField label="Description" name={`projects.${index}.description`} />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <StringListField
                control={control}
                name={`projects.${index}.bullets`}
                label="Bullets"
                addLabel="Add bullet"
              />
              <StringListField
                control={control}
                name={`projects.${index}.technologies`}
                label="Technologies"
                addLabel="Add technology"
              />
            </div>
          </ItemCard>
        ))}
      </div>
    </SectionCard>
  );
}
