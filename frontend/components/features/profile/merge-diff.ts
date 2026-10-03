export const FIELD_KEYS = [
  "contact",
  "headline",
  "summary",
  "skills",
  "experience",
  "projects",
  "education",
  "certifications",
  "awards",
  "extra_sections",
  "preferences",
] as const;

export type FieldKey = (typeof FIELD_KEYS)[number];

export const FIELD_LABELS: Record<FieldKey, string> = {
  contact: "Contact",
  headline: "Headline",
  summary: "Summary",
  skills: "Skills",
  experience: "Experience",
  projects: "Projects",
  education: "Education",
  certifications: "Certifications",
  awards: "Awards",
  extra_sections: "Extra sections",
  preferences: "Preferences",
};

export function summarize(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not set";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.length === 0
      ? "Not set"
      : `${value.length} entr${value.length === 1 ? "y" : "ies"}`;
  }
  const filled = Object.values(value).filter(
    (entry) => entry !== null && entry !== undefined && entry !== "",
  );
  return filled.length === 0 ? "Not set" : `${filled.length} field(s) set`;
}

export function valuesEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
