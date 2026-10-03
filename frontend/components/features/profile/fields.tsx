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

export function DerivedFromExperienceBadge() {
  return <Badge variant="warn">Derived from experience</Badge>;
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
  placeholder?: string | undefined;
}) {
  const { register } = useFormContext<ProfileFormValues>();
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: name as FieldArrayPath<ProfileFormValues>,
  });

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-gray-800">{label}</span>
      {fields.map((field, index) => (
        <div key={field.id} className="flex items-center gap-2">
          <Input
            {...register(`${name}.${index}` as FieldPath<ProfileFormValues>)}
            placeholder={placeholder}
            aria-label={`${label} ${index + 1}`}
          />
          <Button
            variant="secondary"
            className="rounded-full px-2.5 py-1.5 text-xs"
            onClick={() => {
              move(index, index - 1);
            }}
            disabled={index === 0}
            aria-label={`Move ${label} ${index + 1} up`}
          >
            ↑
          </Button>
          <Button
            variant="secondary"
            className="rounded-full px-2.5 py-1.5 text-xs"
            onClick={() => {
              move(index, index + 1);
            }}
            disabled={index === fields.length - 1}
            aria-label={`Move ${label} ${index + 1} down`}
          >
            ↓
          </Button>
          <Button
            variant="danger"
            className="rounded-full px-2.5 py-1.5 text-xs"
            onClick={() => {
              remove(index);
            }}
            aria-label={`Remove ${label} ${index + 1}`}
          >
            ✕
          </Button>
        </div>
      ))}
      <div>
        <Button
          variant="secondary"
          className="rounded-full border-dashed px-4 py-1.5 text-xs font-semibold text-violet-700 hover:border-violet-400 hover:bg-violet-50"
          onClick={() => {
            append("" as never);
          }}
        >
          + {addLabel}
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
  type,
  hint,
  readOnly,
}: {
  label: string;
  name: string;
  error?: string | undefined;
  badge?: ReactNode;
  placeholder?: string | undefined;
  type?: string | undefined;
  hint?: string | undefined;
  readOnly?: boolean;
}) {
  const { register } = useFormContext<ProfileFormValues>();
  return (
    <Field label={label} htmlFor={name} error={error} badge={badge} hint={hint}>
      <Input
        id={name}
        type={type}
        readOnly={readOnly}
        {...register(name as FieldPath<ProfileFormValues>)}
        placeholder={placeholder}
      />
    </Field>
  );
}

const SELECT_STYLES =
  "w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500";

export function SelectField({
  label,
  name,
  options,
  error,
  badge,
  hint,
}: {
  label: string;
  name: string;
  options: readonly { value: string; label: string }[];
  error?: string | undefined;
  badge?: ReactNode;
  hint?: string | undefined;
}) {
  const { register } = useFormContext<ProfileFormValues>();
  return (
    <Field label={label} htmlFor={name} error={error} badge={badge} hint={hint}>
      <select
        id={name}
        className={SELECT_STYLES}
        {...register(name as FieldPath<ProfileFormValues>)}
      >
        <option value="">Not set</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}
