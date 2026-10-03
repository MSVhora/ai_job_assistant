"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import { ExtraIcon } from "./profile-icons";
import { addButtonClass as addBtn, EmptyState, ItemCard, SectionCard } from "./cards";
import { StringListField, TextField } from "./fields";

const emptyExtraSection = { title: "", entries: [] };

export function ExtraSectionsSection() {
  const { control, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "extra_sections" });
  const errors = formState.errors.extra_sections;

  return (
    <SectionCard
      title="Extra sections"
      description="Publications, languages, volunteer work — anything else from the resume"
      icon={<ExtraIcon />}
      defaultOpen={fields.length > 0}
      hasError={errors !== undefined}
      action={
        <Button
          variant="secondary"
          className={addBtn}
          onClick={() => {
            append(emptyExtraSection);
          }}
        >
          + Add section
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="Nothing here yet — add publications, languages, volunteer work or any other resume section."
          action={
            <Button
              variant="secondary"
              className={addBtn}
              onClick={() => {
                append(emptyExtraSection);
              }}
            >
              + Add section
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
              title={field.title || (fields.length > 1 ? `Section ${index + 1}` : undefined)}
            >
              <TextField
                label="Section title"
                name={`extra_sections.${index}.title`}
                placeholder="e.g. Languages"
                error={errors?.[index]?.title?.message}
              />
              <div className="mt-3">
                <StringListField
                  control={control}
                  name={`extra_sections.${index}.entries`}
                  label="Entries"
                  addLabel="Add entry"
                  placeholder="e.g. German — fluent"
                />
              </div>
            </ItemCard>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
