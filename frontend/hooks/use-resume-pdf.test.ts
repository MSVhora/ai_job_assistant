import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { generateResumePdf } from "@/lib/api";

import { useResumePdf } from "./use-resume-pdf";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  generateResumePdf: vi.fn(),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const pdf = (label: string) => new Blob([label], { type: "application/pdf" });

describe("useResumePdf", () => {
  const revoke = vi.fn<(url: string) => void>();

  beforeEach(() => {
    vi.mocked(generateResumePdf).mockReset();
    revoke.mockReset();
    let counter = 0;
    URL.createObjectURL = () => `blob:pdf-${String(++counter)}`;
    URL.revokeObjectURL = revoke;
  });

  it("requests nothing until generate is called", () => {
    const { result } = renderHook(() => useResumePdf("d1", 3));

    expect(result.current.state).toEqual({ status: "idle" });
    expect(generateResumePdf).not.toHaveBeenCalled();
  });

  it("ignores an older response that finishes after a newer one", async () => {
    const first = deferred<Blob>();
    const second = deferred<Blob>();
    vi.mocked(generateResumePdf)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const { result } = renderHook(() => useResumePdf("d1", 3));

    let firstRun!: Promise<void>;
    let secondRun!: Promise<void>;
    act(() => {
      firstRun = result.current.generate();
      secondRun = result.current.generate();
    });
    await act(async () => {
      second.resolve(pdf("new"));
      await secondRun;
    });
    await act(async () => {
      first.resolve(pdf("old"));
      await firstRun;
    });

    expect(result.current.state).toEqual({ status: "ready", url: "blob:pdf-1", version: 3 });
  });

  it("releases the previous blob url when a new PDF replaces it and on unmount", async () => {
    vi.mocked(generateResumePdf).mockResolvedValue(pdf("x"));
    const { result, unmount } = renderHook(() => useResumePdf("d1", 3));

    await act(() => result.current.generate());
    await act(() => result.current.generate());
    expect(revoke).toHaveBeenCalledWith("blob:pdf-1");

    unmount();
    expect(revoke).toHaveBeenCalledWith("blob:pdf-2");
  });

  it("reports the failure message and can be reset", async () => {
    vi.mocked(generateResumePdf).mockRejectedValue(new Error("cannot fit"));
    const { result } = renderHook(() => useResumePdf("d1", 3));

    await act(() => result.current.generate());
    expect(result.current.state).toEqual({ status: "error", message: "cannot fit" });

    act(() => {
      result.current.reset();
    });
    expect(result.current.state).toEqual({ status: "idle" });
  });
});
