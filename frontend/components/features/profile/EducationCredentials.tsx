"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import { ItemCard, SectionCard, StringListField, TextField } from "./fields";

const emptyEducation = {
  institution: "",
  degree: "",
  field: "",
  start_date: "",
  end_date: "",
};

const emptyCertification = { name: "", issuer: "", issued_date: "" };

const emptyAward = { title: "", issuer: "", issued_date: "" };

const emptyExtraSection = { title: "", entries: [] };

export function EducationSection() {
  const { control, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "education" });
  const errors = formState.errors.education;

  return (
    <SectionCard
      title="Education"
      action={<Button variant="secondary" onClick={() => append(emptyEducation)}>Add education</Button>}
    >
      {fields.length === 0 && <p className="text-sm text-gray-500">No education entries yet.</p>}
      <div className="flex flex-col gap-4">
        {fields.map((field, index) => (
          <ItemCard key={field.id} index={index} count={fields.length} onRemove={() => remove(index)} onMove={move}>
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField
                label="Institution"
                name={`education.${index}.institution`}
                error={errors?.[index]?.institution?.message}
              />
              <TextField label="Degree" name={`education.${index}.degree`} />
              <TextField label="Field of study" name={`education.${index}.field`} />
              <div className="grid grid-cols-2 gap-3">
                <TextField label="Start date" name={`education.${index}.start_date`} />
                <TextField label="End date" name={`education.${index}.end_date`} />
              </div>
            </div>
          </ItemCard>
        ))}
      </div>
    </SectionCard>
  );
}

export function CertificationsSection() {
  const { control, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "certifications" });
  const errors = formState.errors.certifications;

  return (
    <SectionCard
      title="Certifications"
      action={
        <Button variant="secondary" onClick={() => append(emptyCertification)}>
          Add certification
        </Button>
      }
    >
      {fields.length === 0 && <p className="text-sm text-gray-500">No certifications yet.</p>}
      <div className="flex flex-col gap-4">
        {fields.map((field, index) => (
          <ItemCard key={field.id} index={index} count={fields.length} onRemove={() => remove(index)} onMove={move}>
            <div className="grid gap-3 sm:grid-cols-3">
              <TextField
                label="Name"
                name={`certifications.${index}.name`}
                error={errors?.[index]?.name?.message}
              />
              <TextField label="Issuer" name={`certifications.${index}.issuer`} />
              <TextField label="Issued" name={`certifications.${index}.issued_date`} placeholder="2022" />
            </div>
          </ItemCard>
        ))}
      </div>
    </SectionCard>
  );
}

export function AwardsSection() {
  const { control, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "awards" });
  const errors = formState.errors.awards;

  return (
    <SectionCard
      title="Awards"
      action={<Button variant="secondary" onClick={() => append(emptyAward)}>Add award</Button>}
    >
      {fields.length === 0 && <p className="text-sm text-gray-500">No awards yet.</p>}
      <div className="flex flex-col gap-4">
        {fields.map((field, index) => (
          <ItemCard key={field.id} index={index} count={fields.length} onRemove={() => remove(index)} onMove={move}>
            <div className="grid gap-3 sm:grid-cols-3">
              <TextField label="Title" name={`awards.${index}.title`} error={errors?.[index]?.title?.message} />
              <TextField label="Issuer" name={`awards.${index}.issuer`} />
              <TextField label="Issued" name={`awards.${index}.issued_date`} placeholder="2023" />
            </div>
          </ItemCard>
        ))}
      </div>
    </SectionCard>
  );
}

export function ExtraSectionsSection() {
  const { control, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({ control, name: "extra_sections" });
  const errors = formState.errors.extra_sections;

  return (
    <SectionCard
      title="Extra sections"
      action={
        <Button variant="secondary" onClick={() => append(emptyExtraSection)}>
          Add section
        </Button>
      }
    >
      {fields.length === 0 && (
        <p className="text-sm text-gray-500">
          Publications, languages, volunteer work — anything else from the resume.
        </p>
      )}
      <div className="flex flex-col gap-4">
        {fields.map((field, index) => (
          <ItemCard key={field.id} index={index} count={fields.length} onRemove={() => remove(index)} onMove={move}>
            <TextField
              label="Section title"
              name={`extra_sections.${index}.title`}
              error={errors?.[index]?.title?.message}
            />
            <div className="mt-3">
              <StringListField
                control={control}
                name={`extra_sections.${index}.entries`}
                label="Entries"
                addLabel="Add entry"
              />
            </div>
          </ItemCard>
        ))}
      </div>
    </SectionCard>
  );
}
