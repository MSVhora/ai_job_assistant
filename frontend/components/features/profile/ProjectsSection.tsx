"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import { addButtonClass as addBtn, EmptyState, ItemCard, SectionCard } from "./cards";
import { ProjectsIcon } from "./profile-icons";
import { StringListField, TextField } from "./fields";

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
        <Button
          variant="secondary"
          className={addBtn}
          onClick={() => {
            append(emptyProject);
          }}
        >
          + Add project
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No projects yet — add personal, open-source or academic projects."
          action={
            <Button
              variant="secondary"
              className={addBtn}
              onClick={() => {
                append(emptyProject);
              }}
            >
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
              onRemove={() => {
                remove(index);
              }}
              onMove={move}
              title={field.name || (fields.length > 1 ? `Project ${index + 1}` : undefined)}
              subtitle={field.role || undefined}
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <TextField
                  label="Name"
                  name={`projects.${index}.name`}
                  placeholder="e.g. JobMatch"
                  error={errors?.[index]?.name?.message}
                />
                <TextField
                  label="Role"
                  name={`projects.${index}.role`}
                  placeholder="e.g. Creator, Maintainer"
                />
                <TextField label="URL" name={`projects.${index}.url`} placeholder="https://…" />
                <div className="grid grid-cols-2 gap-3">
                  <TextField
                    label="Start date"
                    name={`projects.${index}.start_date`}
                    placeholder="Jan 2024"
                  />
                  <TextField
                    label="End date"
                    name={`projects.${index}.end_date`}
                    placeholder="Present"
                  />
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
