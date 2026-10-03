import { describe, expect, it } from "vitest";

import type { ExtractionRun, SyncRun } from "@/lib/api";

import {
  employerKey,
  employerLabel,
  formatResumeAt,
  isActiveStatus,
  viewExtraction,
  viewSync,
} from "./evidence-progress";

function syncRun(overrides: Partial<SyncRun> = {}): SyncRun {
  return {
    id: "s1",
    status: "running",
    mode: "incremental",
    progress: {},
    rate_limit: {},
    resume_at: null,
    error: null,
    usage: {},
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-03T10:00:00Z",
    ...overrides,
  };
}

describe("viewSync", () => {
  it("reads scopes, warnings, chunks and counters from the loose progress JSON", () => {
    const view = viewSync(
      syncRun({
        progress: {
          items: 12,
          stale_flagged: 2,
          warnings: ["ada/a: no access", 7],
          scopes: {
            "ada/b": { status: "ok", items: 9, filtered: 3 },
            "ada/a": { status: "failed", warning: "no access" },
          },
          chunks: { created: 4, embedded: 3, embed_failed: 1, pending_embedding: 1 },
        },
        usage: { requests: 40 },
      }),
    );

    expect(view.active).toBe(true);
    expect(view.items).toBe(12);
    expect(view.requests).toBe(40);
    expect(view.staleFlagged).toBe(2);
    expect(view.warnings).toEqual(["ada/a: no access"]);
    expect(view.scopes.map((scope) => scope.ref)).toEqual(["ada/a", "ada/b"]);
    expect(view.scopes[0]).toMatchObject({ status: "failed", warning: "no access", items: 0 });
    expect(view.chunks).toEqual({ created: 4, embedded: 3, embedFailed: 1, pending: 1 });
  });

  it("tolerates empty or malformed progress and a chunk error marker", () => {
    const view = viewSync(
      syncRun({
        status: "paused",
        progress: { scopes: "nope", warnings: "nope", chunks: { error: "x" }, items: "many" },
        resume_at: "2026-10-03T12:30:00Z",
        error: "budget used up",
      }),
    );

    expect(view).toMatchObject({ active: false, items: 0, scopes: [], warnings: [], chunks: null });
    expect(view.resumeAt?.toISOString()).toBe("2026-10-03T12:30:00.000Z");
    expect(view.error).toBe("budget used up");
  });
});

describe("viewExtraction", () => {
  const run: ExtractionRun = {
    id: "r1",
    status: "succeeded",
    estimate: {},
    progress: { total: 5, done: 5, failed: 1, achievements: 4, rejected: 2, cached: 1 },
    usage: { prompt_tokens: 1200, cost_usd: 0.0123 },
    error: null,
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-03T10:00:00Z",
  };

  it("summarizes counters and cost", () => {
    expect(viewExtraction(run)).toMatchObject({
      active: false,
      total: 5,
      failed: 1,
      achievements: 4,
      promptTokens: 1200,
      costUsd: 0.0123,
    });
  });

  it("reports an unknown cost as null", () => {
    expect(viewExtraction({ ...run, usage: { cost_usd: null } }).costUsd).toBeNull();
  });
});

describe("helpers", () => {
  it("knows which statuses are active", () => {
    expect(isActiveStatus("pending")).toBe(true);
    expect(isActiveStatus("running")).toBe(true);
    expect(isActiveStatus("paused")).toBe(false);
    expect(isActiveStatus(undefined)).toBe(false);
  });

  it("labels and keys employer references", () => {
    expect(employerLabel({ company: "Acme", start_date: "Mar 2021" })).toBe("Acme (Mar 2021)");
    expect(employerLabel({ company: "Acme" })).toBe("Acme");
    expect(employerLabel({ kind: "personal" })).toBe("Personal / open source");
    expect(employerLabel(null)).toBeNull();
    expect(employerKey({ company: "Acme", start_date: "Mar 2021" })).toBe("Acme|Mar 2021");
    expect(employerKey({ kind: "personal" })).toBe("personal");
    expect(employerKey(null)).toBe("");
  });

  it("formats a resume time and rejects invalid dates", () => {
    expect(formatResumeAt(null)).toBeNull();
    expect(formatResumeAt(new Date("nope"))).toBeNull();
    expect(formatResumeAt(new Date("2026-10-03T12:30:00Z"))).toMatch(/\d/);
  });
});
