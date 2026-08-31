import { z } from "zod";

import type { StructuredProfile } from "@/lib/api";

const remotePreference = z.enum(["", "remote", "hybrid", "onsite", "flexible"]);

const numericText = z
  .string()
  .refine((value) => value.trim() === "" || Number.isFinite(Number(value.trim())), {
    message: "Must be a number",
  });

export const profileFormSchema = z
  .object({
    contact: z.object({
      full_name: z.string().min(1, "Full name is required"),
      email: z.string(),
      phone: z.string(),
      location: z.string(),
      links: z.array(
        z.object({
          label: z.string(),
          url: z.string().min(1, "URL is required"),
        }),
      ),
    }),
    headline: z.string(),
    summary: z.string(),
    skills: z.array(z.string()),
    experience: z.array(
      z.object({
        company: z.string(),
        title: z.string(),
        location: z.string(),
        start_date: z.string(),
        end_date: z.string(),
        is_current: z.boolean(),
        bullets: z.array(z.string()),
      }),
    ),
    projects: z.array(
      z.object({
        name: z.string().min(1, "Project name is required"),
        role: z.string(),
        url: z.string(),
        start_date: z.string(),
        end_date: z.string(),
        description: z.string(),
        bullets: z.array(z.string()),
        technologies: z.array(z.string()),
      }),
    ),
    education: z.array(
      z.object({
        institution: z.string(),
        degree: z.string(),
        field: z.string(),
        start_date: z.string(),
        end_date: z.string(),
      }),
    ),
    certifications: z.array(
      z.object({
        name: z.string().min(1, "Name is required"),
        issuer: z.string(),
        issued_date: z.string(),
      }),
    ),
    awards: z.array(
      z.object({
        title: z.string().min(1, "Title is required"),
        issuer: z.string(),
        issued_date: z.string(),
      }),
    ),
    extra_sections: z.array(
      z.object({
        title: z.string().min(1, "Section title is required"),
        entries: z.array(z.string()),
      }),
    ),
    preferences: z.object({
      target_title: z.string(),
      target_location: z.string(),
      remote_preference: remotePreference,
      salary_min: numericText,
      salary_max: numericText,
      currency: z.string(),
    }),
  })
  .superRefine((values, ctx) => {
    const hasContent =
      values.skills.some((skill) => skill.trim() !== "") ||
      values.experience.length > 0 ||
      values.projects.length > 0 ||
      values.awards.length > 0 ||
      values.extra_sections.length > 0;
    if (!hasContent) {
      ctx.addIssue({
        code: "custom",
        message:
          "Profile needs at least one skill, experience, project, award, or extra section entry",
      });
    }
  });

export type ProfileFormValues = z.infer<typeof profileFormSchema>;

type ApiOptionalText = string | null | undefined;

const defaultPreferences = {
  target_title: "",
  target_location: "",
  remote_preference: "" as (typeof remotePreference)["options"][number],
  salary_min: "",
  salary_max: "",
  currency: "",
};

export function toFormValues(profile: StructuredProfile): ProfileFormValues {
  return {
    contact: {
      full_name: profile.contact.full_name,
      email: profile.contact.email ?? "",
      phone: profile.contact.phone ?? "",
      location: profile.contact.location ?? "",
      links: (profile.contact.links ?? []).map((link) => ({
        label: link.label ?? "",
        url: link.url,
      })),
    },
    headline: profile.headline ?? "",
    summary: profile.summary ?? "",
    skills: profile.skills ?? [],
    experience: (profile.experience ?? []).map((item) => ({
      company: item.company ?? "",
      title: item.title ?? "",
      location: item.location ?? "",
      start_date: item.start_date ?? "",
      end_date: item.end_date ?? "",
      is_current: item.is_current ?? false,
      bullets: item.bullets ?? [],
    })),
    projects: (profile.projects ?? []).map((item) => ({
      name: item.name,
      role: item.role ?? "",
      url: item.url ?? "",
      start_date: item.start_date ?? "",
      end_date: item.end_date ?? "",
      description: item.description ?? "",
      bullets: item.bullets ?? [],
      technologies: item.technologies ?? [],
    })),
    education: (profile.education ?? []).map((item) => ({
      institution: item.institution ?? "",
      degree: item.degree ?? "",
      field: item.field ?? "",
      start_date: item.start_date ?? "",
      end_date: item.end_date ?? "",
    })),
    certifications: (profile.certifications ?? []).map((item) => ({
      name: item.name,
      issuer: item.issuer ?? "",
      issued_date: item.issued_date ?? "",
    })),
    awards: (profile.awards ?? []).map((item) => ({
      title: item.title,
      issuer: item.issuer ?? "",
      issued_date: item.issued_date ?? "",
    })),
    extra_sections: (profile.extra_sections ?? []).map((section) => ({
      title: section.title,
      entries: section.entries ?? [],
    })),
    preferences: profile.preferences
      ? {
          target_title: profile.preferences.target_title ?? "",
          target_location: profile.preferences.target_location ?? "",
          remote_preference: (profile.preferences.remote_preference ??
            "") as (typeof remotePreference)["options"][number],
          salary_min: profile.preferences.salary_min?.toString() ?? "",
          salary_max: profile.preferences.salary_max?.toString() ?? "",
          currency: profile.preferences.currency ?? "",
        }
      : { ...defaultPreferences },
  };
}

const optionalText = (value: ApiOptionalText) => {
  const trimmed = (value ?? "").trim();
  return trimmed === "" ? null : trimmed;
};

const cleanList = (values: string[]) =>
  values.map((value) => value.trim()).filter((value) => value !== "");

export function toProfilePayload(values: ProfileFormValues): StructuredProfile {
  const salary = (value: string) => {
    const trimmed = value.trim();
    return trimmed === "" ? null : Number(trimmed);
  };
  const remote = values.preferences.remote_preference;
  const preferences = {
    target_title: optionalText(values.preferences.target_title),
    target_location: optionalText(values.preferences.target_location),
    remote_preference: remote === "" ? null : remote,
    salary_min: salary(values.preferences.salary_min),
    salary_max: salary(values.preferences.salary_max),
    currency: optionalText(values.preferences.currency),
  };
  const hasPreferences = Object.values(preferences).some((value) => value !== null);

  return {
    contact: {
      full_name: values.contact.full_name.trim(),
      email: optionalText(values.contact.email),
      phone: optionalText(values.contact.phone),
      location: optionalText(values.contact.location),
      links: values.contact.links
        .filter((link) => link.url.trim() !== "")
        .map((link) => ({
          label: optionalText(link.label),
          url: link.url.trim(),
        })),
    },
    headline: optionalText(values.headline),
    summary: optionalText(values.summary),
    skills: cleanList(values.skills),
    experience: values.experience
      .filter(
        (item) =>
          item.company.trim() !== "" ||
          item.title.trim() !== "" ||
          item.bullets.some((bullet) => bullet.trim() !== ""),
      )
      .map((item) => ({
        company: optionalText(item.company),
        title: optionalText(item.title),
        location: optionalText(item.location),
        start_date: optionalText(item.start_date),
        end_date: optionalText(item.end_date),
        is_current: item.is_current,
        bullets: cleanList(item.bullets),
      })),
    projects: values.projects
      .filter((item) => item.name.trim() !== "")
      .map((item) => ({
        name: item.name.trim(),
        role: optionalText(item.role),
        url: optionalText(item.url),
        start_date: optionalText(item.start_date),
        end_date: optionalText(item.end_date),
        description: optionalText(item.description),
        bullets: cleanList(item.bullets),
        technologies: cleanList(item.technologies),
      })),
    education: values.education
      .filter((item) => item.institution.trim() !== "")
      .map((item) => ({
        institution: optionalText(item.institution),
        degree: optionalText(item.degree),
        field: optionalText(item.field),
        start_date: optionalText(item.start_date),
        end_date: optionalText(item.end_date),
      })),
    certifications: values.certifications
      .filter((item) => item.name.trim() !== "")
      .map((item) => ({
        name: item.name.trim(),
        issuer: optionalText(item.issuer),
        issued_date: optionalText(item.issued_date),
      })),
    awards: values.awards
      .filter((item) => item.title.trim() !== "")
      .map((item) => ({
        title: item.title.trim(),
        issuer: optionalText(item.issuer),
        issued_date: optionalText(item.issued_date),
      })),
    extra_sections: values.extra_sections
      .filter((section) => section.title.trim() !== "")
      .map((section) => ({
        title: section.title.trim(),
        entries: cleanList(section.entries),
      }))
      .filter((section) => section.entries.length > 0),
    preferences: hasPreferences ? preferences : null,
  };
}
