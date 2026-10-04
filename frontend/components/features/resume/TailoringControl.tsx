"use client";

import type { UseFormRegister } from "react-hook-form";

import { TAILORING_OPTIONS, type CreateFormValues } from "./create-form-schema";

export function TailoringControl({ register }: { register: UseFormRegister<CreateFormValues> }) {
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="text-sm font-medium text-gray-700">Tailoring strength</legend>
      <div className="flex flex-wrap gap-2">
        {TAILORING_OPTIONS.map((option) => (
          <label
            key={option.value}
            className="flex cursor-pointer items-center gap-2 rounded-full border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 has-[:checked]:border-violet-500 has-[:checked]:bg-violet-50 has-[:checked]:font-semibold has-[:checked]:text-violet-800 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-violet-600"
          >
            <input
              type="radio"
              value={option.value}
              className="sr-only"
              {...register("tailoring_strength")}
            />
            {option.label}
            {option.value === "balanced" && (
              <span className="text-xs font-normal text-gray-500">(default)</span>
            )}
          </label>
        ))}
      </div>
      <p className="text-xs text-gray-500">
        How much the job description should boost aligned work. Work that doesn&apos;t match the JD
        is still included by its own priority.
      </p>
    </fieldset>
  );
}
