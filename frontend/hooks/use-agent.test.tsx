import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { message, session } from "@/components/features/chat/fixtures";
import { ApiError, sendAgentMessage } from "@/lib/api";

import { useSendMessage } from "./use-agent";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  sendAgentMessage: vi.fn(),
}));

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  client.setQueryData(
    ["agent-session", "s1"],
    session({ messages: [message("m0", "user", "Hi")] }),
  );
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useSendMessage("s1"), { wrapper });
  const contents = () =>
    client
      .getQueryData<ReturnType<typeof session>>(["agent-session", "s1"])
      ?.messages.map((entry) => entry.content);
  return { result, contents };
}

describe("useSendMessage", () => {
  beforeEach(() => {
    vi.mocked(sendAgentMessage).mockReset();
  });

  it("shows the question at once and replaces it with the stored turn", async () => {
    let resolve!: (turn: Awaited<ReturnType<typeof sendAgentMessage>>) => void;
    vi.mocked(sendAgentMessage).mockReturnValue(
      new Promise((res) => {
        resolve = res;
      }),
    );
    const { result, contents } = setup();

    act(() => {
      result.current.mutate("Why Kafka?");
    });
    await waitFor(() => {
      expect(contents()).toEqual(["Hi", "Why Kafka?"]);
    });

    resolve({
      user_message: message("m1", "user", "Why Kafka?"),
      assistant_message: message("m2", "assistant", "Because of volume."),
    });
    await waitFor(() => {
      expect(contents()).toEqual(["Hi", "Why Kafka?", "Because of volume."]);
    });
  });

  it("takes the question back out when the request fails", async () => {
    vi.mocked(sendAgentMessage).mockRejectedValue(new ApiError(502, "provider down"));
    const { result, contents } = setup();

    act(() => {
      result.current.mutate("Why Kafka?");
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(contents()).toEqual(["Hi"]);
  });
});
