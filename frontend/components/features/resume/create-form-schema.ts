import { z } from "zod";

import type { ResumeDocumentCreate } from "@/lib/api";

export const MAX_JD_CHARS = 20_000;

export const LENGTH_OPTIONS = [
  { value: "1", label: "1 page" },
  { value: "2", label: "2 pages" },
  { value: "3", label: "3 pages" },
  { value: "4", label: "4 pages" },
] as const;

export const TEMPLATE_OPTIONS = [
  { value: "classic", label: "Classic — centered header, roomier spacing" },
  { value: "compact", label: "Compact — left-aligned, tighter spacing" },
] as const;

export const TAILORING_OPTIONS = [
  { value: "light", label: "Light" },
  { value: "balanced", label: "Balanced" },
  { value: "strong", label: "Strong" },
] as const;

export const createFormSchema = z
  .object({
    profile_id: z.string().min(1, "Choose a profile"),
    page_target: z.enum(["1", "2", "3", "4"]),
    template: z.enum(["classic", "compact"]),
    jd_mode: z.enum(["none", "paste", "match"]),
    job_description: z
      .string()
      .max(MAX_JD_CHARS, "Keep the job description under 20,000 characters"),
    match_id: z.string(),
    tailoring_strength: z.enum(["light", "balanced", "strong"]),
    exclude_private: z.boolean(),
  })
  .superRefine((values, context) => {
    if (values.jd_mode === "paste" && values.job_description.trim() === "") {
      context.addIssue({
        code: "custom",
        path: ["job_description"],
        message: "Paste the job description, or choose “No job description”",
      });
    }
    if (values.jd_mode === "match" && values.match_id === "") {
      context.addIssue({ code: "custom", path: ["match_id"], message: "Choose a match" });
    }
  });

export type CreateFormValues = z.infer<typeof createFormSchema>;

export function defaultCreateValues(profileId: string, matchId: string | null): CreateFormValues {
  return {
    profile_id: profileId,
    page_target: "1",
    template: "classic",
    jd_mode: matchId === null ? "none" : "match",
    job_description: "",
    match_id: matchId ?? "",
    tailoring_strength: "balanced",
    exclude_private: false,
  };
}

/** Only keys that apply are sent: no job description, no tailoring strength. */
export function toCreatePayload(values: CreateFormValues): ResumeDocumentCreate {
  const payload: ResumeDocumentCreate = {
    profile_id: values.profile_id,
    page_target: Number(values.page_target),
    template: values.template,
    exclude_private: values.exclude_private,
  };
  if (values.jd_mode === "paste") {
    payload.job_description = values.job_description.trim();
    payload.tailoring_strength = values.tailoring_strength;
  }
  if (values.jd_mode === "match") {
    payload.match_id = values.match_id;
    payload.tailoring_strength = values.tailoring_strength;
  }
  return payload;
}
