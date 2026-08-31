"use client";

import {
  useFieldArray,
  useFormContext,
  type Control,
  type FieldArrayPath,
  type FieldPath,
} from "react-hook-form";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { ProfileFormValues } from "@/lib/profile-schema";

export function AiExtractedBadge() {
  return <Badge variant="ai">AI-extracted</Badge>;
}

export function SectionCard({
  title,
  badge,
  action,
  children,
}: {
  title: string;
  badge?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
          {badge}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function ItemCard({
  index,
  count,
  onRemove,
  onMove,
  children,
}: {
  index: number;
  count: number;
  onRemove: () => void;
  onMove: (from: number, to: number) => void;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div className="mb-3 flex justify-end gap-1">
        <Button
          variant="secondary"
          className="px-2 py-1"
          onClick={() => onMove(index, index - 1)}
          disabled={index === 0}
          aria-label="Move up"
        >
          ↑
        </Button>
        <Button
          variant="secondary"
          className="px-2 py-1"
          onClick={() => onMove(index, index + 1)}
          disabled={index === count - 1}
          aria-label="Move down"
        >
          ↓
        </Button>
        <Button variant="danger" className="px-2 py-1" onClick={onRemove} aria-label="Remove entry">
          Remove
        </Button>
      </div>
      {children}
    </div>
  );
}

export function StringListField({
  control,
  name,
  label,
  addLabel,
  placeholder,
}: {
  control: Control<ProfileFormValues>;
  name: string;
  label: string;
  addLabel: string;
  placeholder?: string;
}) {
  const { register } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: name as FieldArrayPath<ProfileFormValues>,
  });

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{label}</span>
      {fields.map((field, index) => (
        <div key={field.id} className="flex items-center gap-2">
          <Input
            {...register(`${name}.${index}` as FieldPath<ProfileFormValues>)}
            placeholder={placeholder}
            aria-label={`${label} ${index + 1}`}
          />
          <Button
            variant="secondary"
            className="px-2 py-1"
            onClick={() => move(index, index - 1)}
            disabled={index === 0}
            aria-label={`Move ${label} ${index + 1} up`}
          >
            ↑
          </Button>
          <Button
            variant="secondary"
            className="px-2 py-1"
            onClick={() => move(index, index + 1)}
            disabled={index === fields.length - 1}
            aria-label={`Move ${label} ${index + 1} down`}
          >
            ↓
          </Button>
          <Button
            variant="danger"
            className="px-2 py-1"
            onClick={() => remove(index)}
            aria-label={`Remove ${label} ${index + 1}`}
          >
            ✕
          </Button>
        </div>
      ))}
      <div>
        <Button variant="secondary" onClick={() => append("" as never)}>
          {addLabel}
        </Button>
      </div>
    </div>
  );
}

export function TextField({
  label,
  name,
  error,
  badge,
  placeholder,
}: {
  label: string;
  name: string;
  error?: string;
  badge?: ReactNode;
  placeholder?: string;
}) {
  const { register } = useFormContext<ProfileFormValues>();
  return (
    <Field label={label} htmlFor={name} error={error} badge={badge}>
      <Input
        id={name}
        {...register(name as FieldPath<ProfileFormValues>)}
        placeholder={placeholder}
      />
    </Field>
  );
}
