import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { updateGithubScopes } from "@/lib/api";

import { useUpdateScopes } from "./use-evidence-sync";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  updateGithubScopes: vi.fn(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useUpdateScopes", () => {
  beforeEach(() => {
    vi.mocked(updateGithubScopes).mockReset();
    vi.mocked(updateGithubScopes).mockResolvedValue([]);
  });

  it("sends a large selection in batches the API accepts, carrying the acknowledgement", async () => {
    const scopes = Array.from({ length: 450 }, (_, index) => ({
      ref: `acme/repo-${String(index)}`,
      enabled: true,
    }));
    const { result } = renderHook(() => useUpdateScopes(), { wrapper });

    await act(() => result.current.mutateAsync({ scopes, acknowledged: true }));

    expect(vi.mocked(updateGithubScopes).mock.calls.map(([batch]) => batch.length)).toEqual([
      200, 200, 50,
    ]);
    expect(vi.mocked(updateGithubScopes).mock.calls.every(([, ack]) => ack)).toBe(true);
  });
});
