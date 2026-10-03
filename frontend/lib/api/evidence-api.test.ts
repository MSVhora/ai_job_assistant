import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  apiFetchVoid,
  bulkApprove,
  confirmMetric,
  createLink,
  deleteNote,
  editAchievement,
  estimateExtraction,
  listAchievementsPage,
  listNotes,
  listRevisions,
  mergeAchievements,
  runAchievementAction,
  startExtraction,
  startGithubSync,
  unlinkEvidence,
  updateGithubScopes,
} from "@/lib/api";

const fetchMock = vi.fn<typeof fetch>();

function respond(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function lastCall() {
  const [url, init] = fetchMock.mock.calls.at(-1) ?? [];
  return {
    url: typeof url === "string" ? url : url instanceof URL ? url.href : (url?.url ?? ""),
    method: init?.method ?? "GET",
    body: typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined,
  };
}

describe("evidence and achievement API clients", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts a sync with the chosen mode", async () => {
    fetchMock.mockResolvedValue(respond({ sync_id: "s1", status: "pending" }, { status: 202 }));

    await startGithubSync("full");

    expect(lastCall()).toMatchObject({
      url: expect.stringContaining("/api/evidence/github/sync") as unknown,
      method: "POST",
      body: { mode: "full" },
    });
  });

  it("updates scopes with the disclosure flag using PATCH (never PUT)", async () => {
    fetchMock.mockResolvedValue(respond([]));

    await updateGithubScopes([{ ref: "ada/secret", enabled: true }], true);

    expect(lastCall()).toMatchObject({
      method: "PATCH",
      body: { scopes: [{ ref: "ada/secret", enabled: true }], acknowledged_disclosure: true },
    });
  });

  it("reads the total count header for notes", async () => {
    fetchMock.mockResolvedValue(respond([], { headers: { "X-Total-Count": "7" } }));

    const result = await listNotes();

    expect(result.total).toBe(7);
  });

  it("deletes a note without parsing a body", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(deleteNote("n 1")).resolves.toBeUndefined();

    expect(lastCall()).toMatchObject({
      url: expect.stringContaining("/api/evidence/notes/n%201") as unknown,
      method: "DELETE",
    });
  });

  it("raises the server's message on failures of body-less calls", async () => {
    fetchMock.mockResolvedValue(respond({ detail: "evidence item not found" }, { status: 404 }));

    await expect(apiFetchVoid("/api/evidence/notes/x", { method: "DELETE" })).rejects.toThrow(
      "evidence item not found",
    );
  });

  it("creates a link and starts an extraction with the confirmed estimate id", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond({})));

    await createLink({ url: "https://example.com" });
    expect(lastCall().body).toEqual({ url: "https://example.com" });

    await estimateExtraction();
    expect(lastCall()).toMatchObject({ method: "POST" });

    await startExtraction("a".repeat(64));
    expect(lastCall().body).toEqual({ confirmed_estimate_id: "a".repeat(64) });
  });

  it("lists achievements with only the filters that were set", async () => {
    fetchMock.mockResolvedValue(respond([], { headers: { "X-Total-Count": "0" } }));

    await listAchievementsPage({ status: "approved", stale: true, limit: 20, offset: 0 });

    const { url } = lastCall();
    expect(url).toContain("status=approved");
    expect(url).toContain("stale=true");
    expect(url).toContain("limit=20");
    expect(url).not.toContain("private");
    expect(url).not.toContain("undefined");
  });

  it("posts each status action to its own route", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond({})));

    for (const action of [
      "approve",
      "reject",
      "archive",
      "unapprove",
      "restore",
      "acknowledge",
    ] as const) {
      await runAchievementAction("a 1", action);
      expect(lastCall()).toMatchObject({
        url: expect.stringContaining(`/api/achievements/a%201/${action}`) as unknown,
        method: "POST",
      });
    }
  });

  it("sends edits, metric confirmations, merges and bulk approvals as JSON", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond({})));

    await editAchievement("a1", { difficulty: 4 });
    expect(lastCall()).toMatchObject({ method: "PATCH", body: { difficulty: 4 } });

    await confirmMetric("a1", { index: 1, mode: "edit", text: "9x" });
    expect(lastCall().body).toEqual({ index: 1, mode: "edit", text: "9x" });

    await mergeAchievements({ ids: ["a1", "a2"], title: "Merged" });
    expect(lastCall()).toMatchObject({
      url: expect.stringContaining("/api/achievements/merge") as unknown,
      body: { ids: ["a1", "a2"], title: "Merged" },
    });

    await bulkApprove(["a1"]);
    expect(lastCall().body).toEqual({ ids: ["a1"] });
  });

  it("unlinks evidence with DELETE and asks for bounded revisions", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond({})));

    await unlinkEvidence("a1", "i1");
    expect(lastCall()).toMatchObject({
      url: expect.stringContaining("/api/achievements/a1/evidence/i1") as unknown,
      method: "DELETE",
    });

    await listRevisions("a1");
    expect(lastCall().url).toContain("/revisions?limit=100");
  });
});
