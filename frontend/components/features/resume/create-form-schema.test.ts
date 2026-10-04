import { describe, expect, it } from "vitest";

import {
  createFormSchema,
  defaultCreateValues,
  toCreatePayload,
  type CreateFormValues,
} from "./create-form-schema";

function values(overrides: Partial<CreateFormValues> = {}): CreateFormValues {
  return { ...defaultCreateValues("p1", null), ...overrides };
}

describe("createFormSchema", () => {
  it("accepts the defaults for a resume without a job description", () => {
    expect(createFormSchema.safeParse(values()).success).toBe(true);
  });

  it("requires a profile", () => {
    const result = createFormSchema.safeParse(values({ profile_id: "" }));

    expect(result.error?.issues[0]?.message).toBe("Choose a profile");
  });

  it("requires pasted text when pasting and a match when choosing one", () => {
    const pasted = createFormSchema.safeParse(values({ jd_mode: "paste", job_description: "  " }));
    const matched = createFormSchema.safeParse(values({ jd_mode: "match" }));

    expect(pasted.error?.issues[0]?.path).toEqual(["job_description"]);
    expect(matched.error?.issues[0]?.path).toEqual(["match_id"]);
  });

  it("rejects a job description over the backend limit", () => {
    const result = createFormSchema.safeParse(
      values({ jd_mode: "paste", job_description: "x".repeat(20_001) }),
    );

    expect(result.success).toBe(false);
  });
});

describe("toCreatePayload", () => {
  it("omits the job description keys and the tailoring strength when there is none", () => {
    expect(toCreatePayload(values({ page_target: "2" }))).toEqual({
      profile_id: "p1",
      page_target: 2,
      template: "classic",
      exclude_private: false,
    });
  });

  it("sends the trimmed paste with the tailoring strength", () => {
    const payload = toCreatePayload(
      values({
        jd_mode: "paste",
        job_description: "  We run Snowflake  ",
        tailoring_strength: "strong",
      }),
    );

    expect(payload).toMatchObject({
      job_description: "We run Snowflake",
      tailoring_strength: "strong",
    });
    expect(payload).not.toHaveProperty("match_id");
  });

  it("sends the match id and ignores stale pasted text", () => {
    const payload = toCreatePayload(
      values({ jd_mode: "match", match_id: "m1", job_description: "old paste" }),
    );

    expect(payload).toMatchObject({ match_id: "m1", tailoring_strength: "balanced" });
    expect(payload).not.toHaveProperty("job_description");
  });

  it("pre-selects the match tab when arriving from a match", () => {
    expect(defaultCreateValues("p1", "m9")).toMatchObject({ jd_mode: "match", match_id: "m9" });
  });
});
