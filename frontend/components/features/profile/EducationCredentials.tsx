"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import {
  AwardsIcon,
  CertificationsIcon,
  EducationIcon,
  EmptyState,
  ExtraIcon,
  ItemCard,
  SectionCard,
  StringListField,
  TextField,
} from "./fields";

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

const addBtn =
  "rounded-full border-dashed px-4 py-1.5 text-xs font-semibold text-violet-700 hover:border-violet-400 hover:bg-violet-50";

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
        <Button variant="secondary" className={addBtn} onClick={() => append(emptyEducation)}>
          + Add education
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No education entries yet — add your degrees, bootcamps or courses."
          action={
            <Button variant="secondary" className={addBtn} onClick={() => append(emptyEducation)}>
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
              onRemove={() => remove(index)}
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
                <TextField label="Degree" name={`education.${index}.degree`} placeholder="e.g. BSc Computer Science" />
                <TextField label="Field of study" name={`education.${index}.field`} placeholder="e.g. Software Engineering" />
                <div className="grid grid-cols-2 gap-3">
                  <TextField label="Start date" name={`education.${index}.start_date`} placeholder="2020" />
                  <TextField label="End date" name={`education.${index}.end_date`} placeholder="2024" />
                </div>
              </div>
            </ItemCard>
          ))}
        </div>
      )}
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
      description="Licences and certificates with issuer and year"
      icon={<CertificationsIcon />}
      defaultOpen={fields.length > 0}
      hasError={errors !== undefined}
      action={
        <Button variant="secondary" className={addBtn} onClick={() => append(emptyCertification)}>
          + Add certification
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No certifications yet — add AWS, Azure, Scrum and similar credentials."
          action={
            <Button variant="secondary" className={addBtn} onClick={() => append(emptyCertification)}>
              + Add certification
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
              title={field.name || (fields.length > 1 ? `Certification ${index + 1}` : undefined)}
              subtitle={field.issuer || undefined}
            >
              <div className="grid gap-3 sm:grid-cols-3">
                <TextField
                  label="Name"
                  name={`certifications.${index}.name`}
                  placeholder="e.g. AWS Solutions Architect"
                  error={errors?.[index]?.name?.message}
                />
                <TextField label="Issuer" name={`certifications.${index}.issuer`} placeholder="e.g. Amazon" />
                <TextField label="Issued" name={`certifications.${index}.issued_date`} placeholder="2022" />
              </div>
            </ItemCard>
          ))}
        </div>
      )}
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
      description="Prizes, honours and recognitions"
      icon={<AwardsIcon />}
      defaultOpen={fields.length > 0}
      hasError={errors !== undefined}
      action={
        <Button variant="secondary" className={addBtn} onClick={() => append(emptyAward)}>
          + Add award
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No awards yet — add hackathon wins, scholarships or employee-of-the-month style recognitions."
          action={
            <Button variant="secondary" className={addBtn} onClick={() => append(emptyAward)}>
              + Add award
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
              title={field.title || (fields.length > 1 ? `Award ${index + 1}` : undefined)}
              subtitle={field.issuer || undefined}
            >
              <div className="grid gap-3 sm:grid-cols-3">
                <TextField label="Title" name={`awards.${index}.title`} placeholder="e.g. Hackathon winner" error={errors?.[index]?.title?.message} />
                <TextField label="Issuer" name={`awards.${index}.issuer`} placeholder="e.g. TechCrunch" />
                <TextField label="Issued" name={`awards.${index}.issued_date`} placeholder="2023" />
              </div>
            </ItemCard>
          ))}
        </div>
      )}
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
      description="Publications, languages, volunteer work — anything else from the resume"
      icon={<ExtraIcon />}
      defaultOpen={fields.length > 0}
      hasError={errors !== undefined}
      action={
        <Button variant="secondary" className={addBtn} onClick={() => append(emptyExtraSection)}>
          + Add section
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="Nothing here yet — add publications, languages, volunteer work or any other resume section."
          action={
            <Button variant="secondary" className={addBtn} onClick={() => append(emptyExtraSection)}>
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
              onRemove={() => remove(index)}
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
