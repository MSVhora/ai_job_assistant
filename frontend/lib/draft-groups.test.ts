import { describe, expect, it } from "vitest";

import type { EmployerGroup } from "@/lib/api";

import {
  choiceLabel,
  employerChoice,
  employerParams,
  employerRepositories,
  viewIds,
} from "./draft-groups";

const GROUPS: EmployerGroup[] = [
  {
    kind: "employer",
    label: "Acme",
    total: 3,
    eligible: 2,
    repositories: [
      {
        project_key: "acme/api",
        total: 2,
        eligible: 1,
        draft_ids: ["a1", "a2"],
        eligible_ids: ["a1"],
      },
      { project_key: "acme/web", total: 1, eligible: 1, draft_ids: ["a3"], eligible_ids: ["a3"] },
    ],
  },
  {
    kind: "personal",
    label: "Personal",
    total: 1,
    eligible: 0,
    repositories: [
      { project_key: "me/tool", total: 1, eligible: 0, draft_ids: ["p1"], eligible_ids: [] },
    ],
  },
];

describe("draft groups", () => {
  it("encodes a group as a filter choice and back into list params", () => {
    expect(GROUPS.map(employerChoice)).toEqual(["employer:Acme", "personal"]);
    expect(employerParams("employer:Acme")).toEqual({ employer: "Acme" });
    expect(employerParams("personal")).toEqual({ employer_kind: "personal" });
    expect(employerParams("unassigned")).toEqual({ employer_kind: "unassigned" });
    expect(employerParams("")).toEqual({});
  });

  it("collects the ids of the current view", () => {
    expect(viewIds(GROUPS, "employer:Acme", "")).toEqual({
      drafts: ["a1", "a2", "a3"],
      eligible: ["a1", "a3"],
    });
    expect(viewIds(GROUPS, "employer:Acme", "acme/api")).toEqual({
      drafts: ["a1", "a2"],
      eligible: ["a1"],
    });
    expect(viewIds(GROUPS, "", "me/tool")).toEqual({ drafts: ["p1"], eligible: [] });
  });

  it("names the chosen employer", () => {
    expect(choiceLabel(GROUPS, "personal")).toBe("Personal");
    expect(choiceLabel(GROUPS, "")).toBe("all employers");
  });

  it("limits the repositories to those of the chosen employer", () => {
    expect(employerRepositories(GROUPS, "")).toBeUndefined();
    expect(employerRepositories(GROUPS, "employer:Acme")).toEqual(
      new Set(["acme/api", "acme/web"]),
    );
    expect(employerRepositories(GROUPS, "employer:Nobody")).toEqual(new Set());
  });
});
