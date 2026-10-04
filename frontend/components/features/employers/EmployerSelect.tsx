"use client";

import { useState } from "react";

import { Select } from "@/components/ui/select";
import type { EmployerOption } from "@/lib/api";
import { optionKey } from "@/lib/employer-options";

import { AddEmployerDialog } from "./AddEmployerDialog";

const ADD = "__add_employer__";

/** One choice per employer, with a way to add one that is not on the resume. */
export function EmployerSelect({
  id,
  ariaLabel,
  value,
  options,
  noneLabel,
  disabled,
  className,
  onChange,
}: {
  id?: string | undefined;
  ariaLabel?: string | undefined;
  value: string;
  options: EmployerOption[];
  noneLabel: string;
  disabled?: boolean | undefined;
  className?: string | undefined;
  onChange: (key: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  return (
    <>
      <Select
        id={id}
        aria-label={ariaLabel}
        value={value}
        disabled={disabled}
        className={className}
        onChange={(event) => {
          if (event.target.value === ADD) setAdding(true);
          else onChange(event.target.value);
        }}
      >
        <option value="">{noneLabel}</option>
        {options.map((option) => (
          <option key={optionKey(option)} value={optionKey(option)}>
            {option.label}
          </option>
        ))}
        <option value={ADD}>+ Add an employer…</option>
      </Select>
      <AddEmployerDialog
        open={adding}
        onClose={() => {
          setAdding(false);
        }}
        onAdded={onChange}
      />
    </>
  );
}
