import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  addResumeComment,
  createResumeDocument,
  exportResumeDocument,
  listResumeDocuments,
  regenerateResumeDocument,
  removeResumeBullet,
  generateResumePdf,
  resolveResumeConflict,
  updateResumeTemplate,
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

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("resume document api", () => {
  it("creates a document with only the keys it was given", async () => {
    fetchMock.mockResolvedValue(respond({ id: "d1" }, { status: 201 }));

    await createResumeDocument({ profile_id: "p1", page_target: 2, template: "compact" });

    expect(lastCall()).toMatchObject({
      url: expect.stringContaining("/api/resume-documents") as unknown,
      method: "POST",
      body: { profile_id: "p1", page_target: 2, template: "compact" },
    });
  });

  it("lists with a profile filter and reads the total", async () => {
    fetchMock.mockResolvedValue(respond([], { headers: { "X-Total-Count": "3" } }));

    const page = await listResumeDocuments({ profileId: "p 1", limit: 20 });

    expect(lastCall().url).toContain("profile_id=p+1");
    expect(lastCall().url).toContain("limit=20");
    expect(page.total).toBe(3);
  });

  it("regenerates the whole document without a body and one block with one", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond({})));

    await regenerateResumeDocument("d1");
    expect(lastCall()).toMatchObject({ method: "POST", body: undefined });

    await regenerateResumeDocument("d1", "b1");
    expect(lastCall().body).toEqual({ block_id: "b1" });
  });

  it("encodes ids and uses DELETE to remove a bullet", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond({})));

    await removeResumeBullet("d1", "bullet/1");

    expect(lastCall()).toMatchObject({
      method: "DELETE",
      url: expect.stringContaining("/bullets/bullet%2F1") as unknown,
    });
  });

  it("sends comments, template changes and conflict resolutions as JSON", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond({})));

    await addResumeComment("d1", { target: { section: "work", block_id: "b1" }, text: "shorter" });
    expect(lastCall().body).toEqual({
      target: { section: "work", block_id: "b1" },
      text: "shorter",
    });

    await updateResumeTemplate("d1", "compact");
    expect(lastCall()).toMatchObject({ method: "PATCH", body: { template: "compact" } });

    await resolveResumeConflict("d1", "k:1", "keep_as_is");
    expect(lastCall()).toMatchObject({
      url: expect.stringContaining("/conflicts/k%3A1/resolve") as unknown,
      body: { action: "keep_as_is" },
    });
  });

  it("returns exports as text and the rendered PDF as a blob", async () => {
    fetchMock.mockResolvedValueOnce(new Response("# Ada\n", { status: 200 }));
    expect(await exportResumeDocument("d1", "markdown")).toBe("# Ada\n");
    expect(lastCall().url).toContain("/export?format=markdown");

    fetchMock.mockResolvedValueOnce(
      new Response("%PDF-1.7", { status: 200, headers: { "Content-Type": "application/pdf" } }),
    );
    const file = await generateResumePdf("d1");
    expect(file.type).toBe("application/pdf");
    expect(lastCall()).toMatchObject({ method: "POST" });
  });

  it("surfaces the backend detail when a render cannot fit", async () => {
    fetchMock.mockResolvedValue(
      respond({ detail: "this resume cannot fit the chosen page count" }, { status: 422 }),
    );

    const failure: unknown = await generateResumePdf("d1").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({
      status: 422,
      message: expect.stringContaining("cannot fit") as unknown,
    });
  });
});
