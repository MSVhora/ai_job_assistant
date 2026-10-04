import { describe, expect, it } from "vitest";

import { employerOption, PERSONAL_OPTION } from "@/components/features/evidence/fixtures";

import { findOption, findOptionForRef, keyForRef, optionKey, optionRef } from "./employer-options";

const SAMSUNG = employerOption("Samsung", {
  aliases: ["Samsung", "Samsung Research Institute"],
  merged_from: ["Samsung Research Institute"],
});
const ACME = employerOption("Acme Corp", { key: "acme" });
const OPTIONS = [SAMSUNG, ACME, PERSONAL_OPTION];

describe("employer options", () => {
  it("keys an employer by its group and personal work as personal", () => {
    expect(optionKey(ACME)).toBe("acme");
    expect(optionKey(PERSONAL_OPTION)).toBe("personal");
  });

  it("sends a company-level reference, never a single experience entry", () => {
    expect(optionRef(ACME)).toEqual({ company: "Acme Corp" });
    expect(optionRef(PERSONAL_OPTION)).toEqual({ kind: "personal" });
  });

  it("finds an option by its key", () => {
    expect(findOption(OPTIONS, "acme")).toBe(ACME);
    expect(findOption(OPTIONS, "nope")).toBeUndefined();
  });

  it("matches a stored reference to its employer through any of the group's names", () => {
    expect(findOptionForRef(OPTIONS, { company: "Samsung Research Institute" })).toBe(SAMSUNG);
    expect(findOptionForRef(OPTIONS, { company: "  samsung " })).toBe(SAMSUNG);
    expect(findOptionForRef(OPTIONS, { company: "Acme Corp", start_date: "Jan 2020" })).toBe(ACME);
  });

  it("matches personal work and finds nothing for unknown or empty references", () => {
    expect(findOptionForRef(OPTIONS, { kind: "personal" })).toBe(PERSONAL_OPTION);
    expect(findOptionForRef(OPTIONS, { company: "Nowhere" })).toBeUndefined();
    expect(findOptionForRef(OPTIONS, { company: "  " })).toBeUndefined();
    expect(findOptionForRef(OPTIONS, null)).toBeUndefined();
    expect(findOptionForRef(OPTIONS, undefined)).toBeUndefined();
  });

  it("gives the select value for a stored reference, empty when none matches", () => {
    expect(keyForRef(OPTIONS, { company: "Samsung Research Institute" })).toBe("samsung");
    expect(keyForRef(OPTIONS, { kind: "personal" })).toBe("personal");
    expect(keyForRef(OPTIONS, { company: "Nowhere" })).toBe("");
    expect(keyForRef([], { company: "Acme Corp" })).toBe("");
  });
});
