"use client";

import { useFieldArray, useFormContext } from "react-hook-form";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { ProfileFormValues } from "@/lib/profile-schema";

import { SectionCard } from "./cards";
import { TextField } from "./fields";
import { ContactIcon } from "./profile-icons";

const emptyLink = { label: "", url: "" };

export function ContactSection({ aiBadge }: { aiBadge: ReactNode }) {
  const { register, control, formState } = useFormContext<ProfileFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: "contact.links" });
  const errors = formState.errors;

  return (
    <SectionCard
      title="Contact"
      description="How employers can reach you"
      icon={<ContactIcon />}
      badge={aiBadge}
      hasError={errors.contact !== undefined}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Full name"
          name="contact.full_name"
          placeholder="Jane Doe"
          error={errors.contact?.full_name?.message}
          badge={aiBadge}
        />
        <TextField
          label="Email"
          name="contact.email"
          type="email"
          placeholder="jane@example.com"
          error={errors.contact?.email?.message}
          badge={aiBadge}
        />
        <TextField
          label="Phone"
          name="contact.phone"
          placeholder="+1 555 000 0000"
          badge={aiBadge}
        />
        <TextField
          label="Location"
          name="contact.location"
          placeholder="Berlin, Germany"
          badge={aiBadge}
        />
        <TextField
          label="Country code"
          name="contact.country"
          placeholder="in"
          hint="ISO 3166-1 alpha-2, e.g. in."
          error={errors.contact?.country?.message}
          badge={aiBadge}
        />
      </div>
      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-gray-800">Links</span>
          <Button
            variant="secondary"
            className="rounded-full border-dashed px-4 py-1.5 text-xs font-semibold text-violet-700 hover:border-violet-400 hover:bg-violet-50"
            onClick={() => {
              append(emptyLink);
            }}
          >
            + Add link
          </Button>
        </div>
        {fields.length === 0 ? (
          <p className="rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-500">
            No links yet — add LinkedIn, GitHub, or a portfolio URL.
          </p>
        ) : (
          fields.map((field, index) => (
            <div key={field.id} className="mb-2 grid grid-cols-[1fr_2fr_auto] items-start gap-2">
              <Field label="Label" htmlFor={`contact.links.${index}.label`}>
                <Input
                  id={`contact.links.${index}.label`}
                  {...register(`contact.links.${index}.label`)}
                  placeholder="LinkedIn"
                />
              </Field>
              <Field
                label="URL"
                htmlFor={`contact.links.${index}.url`}
                error={errors.contact?.links?.[index]?.url?.message}
              >
                <Input
                  id={`contact.links.${index}.url`}
                  {...register(`contact.links.${index}.url`)}
                  placeholder="https://…"
                />
              </Field>
              <Button
                variant="danger"
                className="mt-7 rounded-full px-2.5 py-1.5 text-xs"
                onClick={() => {
                  remove(index);
                }}
                aria-label={`Remove link ${index + 1}`}
              >
                ✕
              </Button>
            </div>
          ))
        )}
      </div>
    </SectionCard>
  );
}
