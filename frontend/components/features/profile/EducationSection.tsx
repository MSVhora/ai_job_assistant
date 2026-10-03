"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import { EducationIcon } from "./profile-icons";
import { addButtonClass as addBtn, EmptyState, ItemCard, SectionCard } from "./cards";
import { TextField } from "./fields";

const emptyEducation = {
  institution: "",
  degree: "",
  field: "",
  start_date: "",
  end_date: "",
};

export function EducationSection() {
  const { control, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "education" });
  const errors = formState.errors.education;

  return (
    <SectionCard
      title="Education"
      description="Degrees and programmes from your resume"
      icon={<EducationIcon />}
      defaultOpen={fields.length > 0}
      hasError={errors !== undefined}
      action={
        <Button
          variant="secondary"
          className={addBtn}
          onClick={() => {
            append(emptyEducation);
          }}
        >
          + Add education
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No education entries yet — add your degrees, bootcamps or courses."
          action={
            <Button
              variant="secondary"
              className={addBtn}
              onClick={() => {
                append(emptyEducation);
              }}
            >
              + Add education
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
              title={fields.length > 1 ? `Education ${index + 1}` : undefined}
              subtitle={
                field.degree || field.institution
                  ? [field.degree, field.institution].filter(Boolean).join(" · ")
                  : undefined
              }
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <TextField
                  label="Institution"
                  name={`education.${index}.institution`}
                  placeholder="e.g. TU Munich"
                  error={errors?.[index]?.institution?.message}
                />
                <TextField
                  label="Degree"
                  name={`education.${index}.degree`}
                  placeholder="e.g. BSc Computer Science"
                />
                <TextField
                  label="Field of study"
                  name={`education.${index}.field`}
                  placeholder="e.g. Software Engineering"
                />
                <div className="grid grid-cols-2 gap-3">
                  <TextField
                    label="Start date"
                    name={`education.${index}.start_date`}
                    placeholder="2020"
                  />
                  <TextField
                    label="End date"
                    name={`education.${index}.end_date`}
                    placeholder="2024"
                  />
                </div>
              </div>
            </ItemCard>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
