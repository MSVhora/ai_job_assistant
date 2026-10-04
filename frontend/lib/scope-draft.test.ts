import { describe, expect, it } from "vitest";

import { scope } from "@/components/features/evidence/fixtures";

import {
  changeCount,
  chunk,
  filterScopes,
  newlyEnabledPrivate,
  paginate,
  selectScopes,
  selectedCount,
  toUpdates,
  viewOf,
  withPatch,
} from "./scope-draft";

const api = scope({ ref: "acme/api" });
const web = scope({ ref: "acme/web", enabled: true });
const secret = scope({ ref: "ada/secret", is_private: true });
const repos = [api, web, secret];

describe("withPatch", () => {
  it("records a difference from what is saved", () => {
    const draft = withPatch({}, api, { enabled: true });

    expect(draft).toEqual({ "acme/api": { enabled: true } });
    expect(viewOf(api, draft["acme/api"]).enabled).toBe(true);
  });

  it("forgets a repository once it is edited back to the saved value", () => {
    const edited = withPatch({}, web, { enabled: false });
    const restored = withPatch(edited, web, { enabled: true });

    expect(edited).toEqual({ "acme/web": { enabled: false } });
    expect(restored).toEqual({});
  });

  it("keeps several fields of one repository together and prunes only the unchanged one", () => {
    let draft = withPatch({}, api, { enabled: true });
    draft = withPatch(draft, api, { content_level: "metadata_only" });
    draft = withPatch(draft, api, { enabled: false });

    expect(draft).toEqual({ "acme/api": { content_level: "metadata_only" } });
  });

  it("treats an employer change as a difference and an identical mapping as none", () => {
    const mapped = scope({
      ref: "acme/api",
      employer_ref: { company: "Acme", start_date: "2021" },
    });

    const same = withPatch({}, mapped, { employer_ref: { company: "Acme", start_date: "2021" } });
    const personal = withPatch({}, mapped, { employer_ref: { kind: "personal" } });
    const cleared = withPatch({}, mapped, { employer_ref: null });

    expect(same).toEqual({});
    expect(personal).toEqual({ "acme/api": { employer_ref: { kind: "personal" } } });
    expect(cleared).toEqual({ "acme/api": { employer_ref: null } });
  });
});

describe("selection", () => {
  it("selects every given repository and clears them again", () => {
    const all = selectScopes({}, repos, true);

    expect(Object.keys(all).sort()).toEqual(["acme/api", "ada/secret"]);
    expect(selectedCount(repos, all)).toBe(3);
    expect(selectedCount(repos, selectScopes(all, repos, false))).toBe(0);
    expect(changeCount(selectScopes(all, repos, false))).toBe(1);
  });

  it("lists only private repositories that would newly be enabled", () => {
    const draft = selectScopes({}, repos, true);

    expect(newlyEnabledPrivate(draft, repos)).toEqual(["ada/secret"]);
    expect(newlyEnabledPrivate({}, repos)).toEqual([]);
  });

  it("turns the draft into one update per changed repository", () => {
    const draft = withPatch(withPatch({}, api, { enabled: true }), web, {
      content_level: "metadata_only",
    });

    expect(toUpdates(draft)).toEqual([
      { ref: "acme/api", enabled: true },
      { ref: "acme/web", content_level: "metadata_only" },
    ]);
  });
});

describe("filterScopes and chunk", () => {
  it("filters by a case-insensitive part of the name", () => {
    expect(filterScopes(repos, " ACME ").map((item) => item.ref)).toEqual(["acme/api", "acme/web"]);
    expect(filterScopes(repos, "")).toHaveLength(3);
  });

  it("splits updates into batches the API accepts", () => {
    expect(chunk([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
    expect(chunk([], 200)).toEqual([]);
  });
});

describe("paginate", () => {
  const items = Array.from({ length: 55 }, (_, index) => index + 1);

  it("returns one page with its position in the list", () => {
    const second = paginate(items, 1, 25);

    expect(second.items).toHaveLength(25);
    expect(second.items[0]).toBe(26);
    expect([second.from, second.to, second.total, second.pageCount]).toEqual([26, 50, 55, 3]);
  });

  it("gives the last page only what is left", () => {
    const last = paginate(items, 2, 25);

    expect(last.items).toEqual([51, 52, 53, 54, 55]);
    expect([last.from, last.to]).toEqual([51, 55]);
  });

  it("clamps a page that no longer exists, for example after filtering", () => {
    expect(paginate(items.slice(0, 10), 4, 25).page).toBe(0);
    expect(paginate(items, -3, 25).page).toBe(0);
  });

  it("handles an empty list", () => {
    expect(paginate([], 0, 25)).toEqual({
      items: [],
      page: 0,
      pageCount: 1,
      from: 0,
      to: 0,
      total: 0,
    });
  });
});
