"use client";

import { useFieldArray, useFormContext } from "react-hook-form";

import { Button } from "@/components/ui/button";
import type { ProfileFormValues } from "@/lib/profile-schema";

import { AwardsIcon, CertificationsIcon } from "./profile-icons";
import { addButtonClass as addBtn, EmptyState, ItemCard, SectionCard } from "./cards";
import { TextField } from "./fields";

const emptyCertification = { name: "", issuer: "", issued_date: "" };

const emptyAward = { title: "", issuer: "", issued_date: "" };

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
        <Button
          variant="secondary"
          className={addBtn}
          onClick={() => {
            append(emptyCertification);
          }}
        >
          + Add certification
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No certifications yet — add AWS, Azure, Scrum and similar credentials."
          action={
            <Button
              variant="secondary"
              className={addBtn}
              onClick={() => {
                append(emptyCertification);
              }}
            >
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
              onRemove={() => {
                remove(index);
              }}
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
                <TextField
                  label="Issuer"
                  name={`certifications.${index}.issuer`}
                  placeholder="e.g. Amazon"
                />
                <TextField
                  label="Issued"
                  name={`certifications.${index}.issued_date`}
                  placeholder="2022"
                />
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
        <Button
          variant="secondary"
          className={addBtn}
          onClick={() => {
            append(emptyAward);
          }}
        >
          + Add award
        </Button>
      }
    >
      {fields.length === 0 ? (
        <EmptyState
          message="No awards yet — add hackathon wins, scholarships or employee-of-the-month style recognitions."
          action={
            <Button
              variant="secondary"
              className={addBtn}
              onClick={() => {
                append(emptyAward);
              }}
            >
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
              onRemove={() => {
                remove(index);
              }}
              onMove={move}
              title={field.title || (fields.length > 1 ? `Award ${index + 1}` : undefined)}
              subtitle={field.issuer || undefined}
            >
              <div className="grid gap-3 sm:grid-cols-3">
                <TextField
                  label="Title"
                  name={`awards.${index}.title`}
                  placeholder="e.g. Hackathon winner"
                  error={errors?.[index]?.title?.message}
                />
                <TextField
                  label="Issuer"
                  name={`awards.${index}.issuer`}
                  placeholder="e.g. TechCrunch"
                />
                <TextField label="Issued" name={`awards.${index}.issued_date`} placeholder="2023" />
              </div>
            </ItemCard>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
