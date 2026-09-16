"use client";

import {
  useFieldArray,
  useFormContext,
  type Control,
  type FieldArrayPath,
  type FieldPath,
} from "react-hook-form";
import { useState, type ReactNode } from "react";

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

const iconProps = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
  className: "h-4.5 w-4.5",
} as const;

function Svg({ d, children }: { d?: string; children?: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" {...iconProps}>
      {d !== undefined && <path d={d} />}
      {children}
    </svg>
  );
}

export function ContactIcon() {
  return (
    <Svg>
      <path d="M4 6h16v12H4z" />
      <path d="M4 7l8 6 8-6" />
    </Svg>
  );
}

export function HeadlineIcon() {
  return (
    <Svg>
      <path d="M4 6h16M4 12h10M4 18h7" />
    </Svg>
  );
}

export function SkillsIcon() {
  return (
    <Svg>
      <path d="M12 3l2.5 5.5L20 9l-4 4 1 6-5-2.8L7 19l1-6-4-4 5.5-.5z" />
    </Svg>
  );
}

export function ExperienceIcon() {
  return (
    <Svg>
      <rect x="3" y="8" width="18" height="12" rx="2" />
      <path d="M9 8V6a2 2 0 012-2h2a2 2 0 012 2v2M3 13h18" />
    </Svg>
  );
}

export function ProjectsIcon() {
  return (
    <Svg>
      <path d="M4 20V10l8-6 8 6v10" />
      <path d="M10 20v-6h4v6" />
    </Svg>
  );
}

export function EducationIcon() {
  return (
    <Svg>
      <path d="M3 9l9-5 9 5-9 5-9-5z" />
      <path d="M7 11.5V16c0 1.5 2.5 3 5 3s5-1.5 5-3v-4.5" />
    </Svg>
  );
}

export function CertificationsIcon() {
  return (
    <Svg>
      <circle cx="12" cy="9" r="5" />
      <path d="M9 13l-1.5 8L12 19l4.5 2L15 13" />
    </Svg>
  );
}

export function AwardsIcon() {
  return (
    <Svg>
      <path d="M8 21h8M12 17v4" />
      <path d="M7 4h10v4a5 5 0 01-10 0V4z" />
      <path d="M7 6H4a3 3 0 003 3M17 6h3a3 3 0 01-3 3" />
    </Svg>
  );
}

export function ExtraIcon() {
  return (
    <Svg>
      <path d="M6 3h9l4 4v14H6V3z" />
      <path d="M9 12h6M9 16h6M9 8h3" />
    </Svg>
  );
}

export function PreferencesIcon() {
  return (
    <Svg>
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="8" cy="17" r="2" />
    </Svg>
  );
}

export function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className={`h-4 w-4 shrink-0 text-gray-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
    >
      <path
        fillRule="evenodd"
        d="M5.3 7.3a1 1 0 011.4 0L10 10.6l3.3-3.3a1 1 0 111.4 1.4l-4 4a1 1 0 01-1.4 0l-4-4a1 1 0 010-1.4z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function SectionCard({
  title,
  description,
  icon,
  badge,
  action,
  defaultOpen = true,
  hasError = false,
  children,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  badge?: ReactNode;
  action?: ReactNode;
  defaultOpen?: boolean;
  hasError?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-lg shadow-gray-100">
      <div className="flex flex-wrap items-center gap-2 border-b border-gray-100 bg-gray-50/60 px-5 py-4 sm:px-6">
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-xl text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          {icon !== undefined && (
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
              {icon}
            </span>
          )}
          <span className="flex min-w-0 flex-col">
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-base font-bold tracking-tight text-gray-900">{title}</span>
              {badge}
            </span>
            {description !== undefined && (
              <span className="truncate text-xs text-gray-500">{description}</span>
            )}
          </span>
          <span className="ml-auto flex items-center gap-2 pl-2">
            <ChevronIcon open={open} />
          </span>
        </button>
        {action !== undefined && <div className="flex shrink-0 items-center">{action}</div>}
      </div>
      {hasError && !open && (
        <p role="alert" className="border-b border-red-100 bg-red-50 px-6 py-2 text-xs font-medium text-red-700">
          This section has fields that need attention — reopen to review them.
        </p>
      )}
      <div className={open ? "p-5 sm:p-6" : "hidden"}>{children}</div>
    </section>
  );
}

export function ItemCard({
  title,
  subtitle,
  index,
  count,
  onRemove,
  onMove,
  children,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  index: number;
  count: number;
  onRemove: () => void;
  onMove: (from: number, to: number) => void;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50/50 p-4 transition-colors focus-within:border-violet-300 hover:border-violet-200">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-100 text-[11px] font-bold text-violet-700">
            {index + 1}
          </span>
          <div className="min-w-0">
            {title !== undefined && (
              <p className="truncate text-sm font-semibold text-gray-900">{title}</p>
            )}
            {subtitle !== undefined && (
              <p className="truncate text-xs text-gray-500">{subtitle}</p>
            )}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button
            variant="secondary"
            className="rounded-full px-2.5 py-1 text-xs"
            onClick={() => onMove(index, index - 1)}
            disabled={index === 0}
            aria-label="Move up"
          >
            ↑
          </Button>
          <Button
            variant="secondary"
            className="rounded-full px-2.5 py-1 text-xs"
            onClick={() => onMove(index, index + 1)}
            disabled={index === count - 1}
            aria-label="Move down"
          >
            ↓
          </Button>
          <Button
            variant="danger"
            className="rounded-full px-3 py-1 text-xs"
            onClick={onRemove}
            aria-label="Remove entry"
          >
            Remove
          </Button>
        </div>
      </div>
      {children}
    </div>
  );
}

export function EmptyState({ message, action }: { message: string; action: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-violet-200 bg-violet-50/40 px-4 py-6 text-center">
      <p className="text-sm text-gray-500">{message}</p>
      {action}
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
            onClick={() => move(index, index - 1)}
            disabled={index === 0}
            aria-label={`Move ${label} ${index + 1} up`}
          >
            ↑
          </Button>
          <Button
            variant="secondary"
            className="rounded-full px-2.5 py-1.5 text-xs"
            onClick={() => move(index, index + 1)}
            disabled={index === fields.length - 1}
            aria-label={`Move ${label} ${index + 1} down`}
          >
            ↓
          </Button>
          <Button
            variant="danger"
            className="rounded-full px-2.5 py-1.5 text-xs"
            onClick={() => remove(index)}
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
          onClick={() => append("" as never)}
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
  error?: string;
  badge?: ReactNode;
  placeholder?: string;
  type?: string;
  hint?: string;
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
  error?: string;
  badge?: ReactNode;
  hint?: string;
}) {
  const { register } = useFormContext<ProfileFormValues>();
  return (
    <Field label={label} htmlFor={name} error={error} badge={badge} hint={hint}>
      <select id={name} className={SELECT_STYLES} {...register(name as FieldPath<ProfileFormValues>)}>
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
