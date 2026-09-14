"use client";

import { useFormContext } from "react-hook-form";

import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { SourceFilterDecl } from "@/lib/api";

import type { SearchFormValues } from "./search-form-schema";

function FilterControl({
  sourceName,
  decl,
  invalid,
}: {
  sourceName: string;
  decl: SourceFilterDecl;
  invalid: boolean;
}) {
  const { register } = useFormContext<SearchFormValues>();
  const id = `query-${sourceName}-option-${decl.key}`;
  const path = `queries.${sourceName}.options.${decl.key}` as const;

  if (decl.type === "boolean") {
    return (
      <Checkbox
        id={id}
        label={decl.label}
        aria-invalid={invalid || undefined}
        {...register(path)}
      />
    );
  }
  if (decl.type === "select") {
    return (
      <Select id={id} aria-invalid={invalid || undefined} {...register(path)}>
        <option value="">Not set</option>
        {(decl.options ?? []).map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    );
  }
  return (
    <Input
      id={id}
      type={decl.type === "number" ? "number" : "text"}
      min={decl.type === "number" ? 0 : undefined}
      step={decl.type === "number" ? 1 : undefined}
      placeholder={decl.placeholder ?? undefined}
      aria-invalid={invalid || undefined}
      {...register(path)}
    />
  );
}

export function SourceFiltersForm({
  sourceName,
  decls,
}: {
  sourceName: string;
  decls: SourceFilterDecl[];
}) {
  const {
    formState: { errors },
  } = useFormContext<SearchFormValues>();
  const sourceErrors = errors.queries?.[sourceName]?.options;

  return (
    <div className="flex flex-col gap-2.5 rounded-xl bg-gray-50 p-2.5">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        Advanced filters
      </p>
      {decls.map((decl) => {
        const message =
          sourceErrors?.[decl.key]?.message ??
          sourceErrors?.root?.message ??
          sourceErrors?.message;
        return (
          <Field
            key={decl.key}
            label={decl.type === "boolean" ? "" : decl.label}
            htmlFor={`query-${sourceName}-option-${decl.key}`}
            error={typeof message === "string" ? message : undefined}
            hint={decl.help_text ?? undefined}
          >
            <FilterControl
              sourceName={sourceName}
              decl={decl}
              invalid={message !== undefined}
            />
          </Field>
        );
      })}
    </div>
  );
}
