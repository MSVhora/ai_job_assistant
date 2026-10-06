import { describe, expect, it } from "vitest";

import type { StructuredProfile } from "@/lib/api";

import { profileFormSchema, toFormValues, toProfilePayload } from "./profile-schema";

const baseProfile = (contact: Partial<StructuredProfile["contact"]> = {}) =>
  ({
    contact: {
      full_name: "Jane Doe",
      email: null,
      phone: null,
      location: null,
      ...contact,
      links: [],
    },
    headline: null,
    summary: null,
    skills: ["Kotlin"],
    experience: [],
    projects: [],
    education: [],
    certifications: [],
    awards: [],
    extra_sections: [],
    preferences: null,
  }) as unknown as StructuredProfile;

describe("contact country round-trip", () => {
  it("keeps a saved country through form values and the save payload", () => {
    const profile = baseProfile({ country: "in" });
    const values = toFormValues(profile);
    expect(values.contact.country).toBe("in");
    const payload = toProfilePayload(values);
    expect(payload.contact.country).toBe("in");
  });

  it("accepts a chat-set country in the form schema", () => {
    const values = toFormValues(baseProfile({ country: "in" }));
    values.contact.country = "de";
    const parsed = profileFormSchema.safeParse(values);
    expect(parsed.success).toBe(true);
  });

  it("saves a cleared country as null instead of dropping the field", () => {
    const values = toFormValues(baseProfile({ country: "in" }));
    values.contact.country = "";
    const payload = toProfilePayload(values);
    expect(payload.contact.country).toBeNull();
  });

  it("round-trips a profile that has no country yet", () => {
    const values = toFormValues(baseProfile());
    expect(values.contact.country).toBe("");
    const payload = toProfilePayload(values);
    expect(payload.contact.country).toBeNull();
    expect(values.contact.email).toBe("");
    expect(toFormValues(payload).contact.country).toBe("");
  });

  it("rejects country codes with more than two letters", () => {
    const values = toFormValues(baseProfile({ country: "in" }));
    values.contact.country = "germany";
    const parsed = profileFormSchema.safeParse(values);
    expect(parsed.success).toBe(false);
  });
});

describe("derived experience fields (issue #32)", () => {
  it("exposes years_of_experience and seniority_source in form values for display", () => {
    const profile = {
      ...baseProfile(),
      years_of_experience: 7,
      preferences: {
        target_title: null,
        target_location: null,
        remote_preference: null,
        salary_min: null,
        salary_max: null,
        currency: null,
        seniority: "senior",
        seniority_source: "derived",
        work_authorization: null,
      },
    } as unknown as StructuredProfile;

    const values = toFormValues(profile);
    expect(values.years_of_experience).toBe("7");
    expect(values.preferences.seniority_source).toBe("derived");
    expect(values.preferences.seniority).toBe("senior");
  });

  it("never sends the server-derived fields in the save payload", () => {
    const profile = {
      ...baseProfile(),
      years_of_experience: 7,
      preferences: {
        target_title: null,
        target_location: null,
        remote_preference: null,
        salary_min: null,
        salary_max: null,
        currency: null,
        seniority: "senior",
        seniority_source: "derived",
        work_authorization: null,
      },
    } as unknown as StructuredProfile;

    const payload = toProfilePayload(toFormValues(profile)) as Record<string, unknown> & {
      preferences: Record<string, unknown> | null;
    };
    expect("years_of_experience" in payload).toBe(false);
    expect(payload.preferences !== null && "seniority_source" in payload.preferences).toBe(false);
    expect(payload.preferences?.seniority).toBe("senior");
  });
});
