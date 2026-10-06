import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, deleteAgentSession, listAgentSessions } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ChatHistory } from "./ChatHistory";
import { ChatProvider, useChat } from "./ChatProvider";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  listAgentSessions: vi.fn(),
  deleteAgentSession: vi.fn(),
}));

const row = (id: string, title: string) => ({
  id,
  profile_id: "p1",
  match_id: null,
  title,
  style_notes: null,
  created_at: "2026-10-05T10:00:00Z",
  updated_at: "2026-10-05T10:00:00Z",
});

function Active() {
  const { sessionId } = useChat();
  return <p data-testid="active">{sessionId ?? "none"}</p>;
}

function show(onPick?: () => void) {
  return renderWithClient(
    <ChatProvider>
      <ChatHistory {...(onPick ? { onPick } : {})} />
      <Active />
    </ChatProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.clear();
});

describe("ChatHistory", () => {
  it("lists conversations and opens the one you pick", async () => {
    vi.mocked(listAgentSessions).mockResolvedValue({
      items: [row("s2", "Tell me about yourself"), row("s1", "What have I built with Python?")],
      total: 2,
    });
    const onPick = vi.fn();
    show(onPick);

    await userEvent.click(
      await screen.findByRole("button", { name: /^What have I built with Python\?/ }),
    );

    expect(screen.getByTestId("active")).toHaveTextContent("s1");
    expect(onPick).toHaveBeenCalled();
  });

  it("shows an empty state", async () => {
    vi.mocked(listAgentSessions).mockResolvedValue({ items: [], total: 0 });
    show();

    expect(await screen.findByText(/No conversations yet/)).toBeInTheDocument();
  });

  it("shows an error with a retry", async () => {
    vi.mocked(listAgentSessions).mockRejectedValue(new ApiError(0, "network error: down"));
    show();

    expect(await screen.findByRole("alert")).toHaveTextContent("network error: down");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("deletes a conversation and leaves the open one if it was another", async () => {
    vi.mocked(listAgentSessions).mockResolvedValue({
      items: [row("s1", "Tell me about yourself")],
      total: 1,
    });
    vi.mocked(deleteAgentSession).mockResolvedValue(undefined);
    show();

    await userEvent.click(
      await screen.findByRole("button", { name: "Delete conversation Tell me about yourself" }),
    );

    expect(deleteAgentSession).toHaveBeenCalledWith("s1");
  });
});
