import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createAgentSession,
  getAgentSession,
  listAgentSessions,
  listProfiles,
  sendAgentMessage,
  type AgentSessionSummary,
} from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ChatConversation } from "./ChatConversation";
import { ChatProvider, useChat } from "./ChatProvider";
import { citation, grounding, message, session } from "./fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  createAgentSession: vi.fn(),
  getAgentSession: vi.fn(),
  sendAgentMessage: vi.fn(),
  listAgentSessions: vi.fn(),
  listProfiles: vi.fn(),
}));
vi.mock("@/hooks/use-evidence-sources", () => ({
  useCreateNote: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

function Harness({ initial }: { initial: string | null }) {
  const { sessionId, setSessionId, setProfileId } = useChat();
  return (
    <>
      <button
        type="button"
        onClick={() => {
          setProfileId("p1");
          setSessionId(initial);
        }}
      >
        init
      </button>
      <p data-testid="active">{sessionId ?? "none"}</p>
      <ChatConversation sessionId={sessionId} />
    </>
  );
}

async function show(initial: string | null = null) {
  renderWithClient(
    <ChatProvider>
      <Harness initial={initial} />
    </ChatProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "init" }));
}

const summary = (id: string): AgentSessionSummary => ({
  id,
  profile_id: "p1",
  match_id: null,
  title: "x",
  style_notes: null,
  created_at: "2026-10-05T10:00:00Z",
  updated_at: "2026-10-05T10:00:00Z",
});

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.clear();
  vi.mocked(listProfiles).mockResolvedValue([]);
  vi.mocked(listAgentSessions).mockResolvedValue({ items: [], total: 0 });
});

describe("ChatConversation", () => {
  it("shows starter questions in a new chat and fills the input from one", async () => {
    await show();

    await userEvent.click(screen.getByRole("button", { name: "Tell me about yourself" }));

    expect(screen.getByRole("textbox", { name: "Your question" })).toHaveValue(
      "Tell me about yourself.",
    );
    expect(createAgentSession).not.toHaveBeenCalled();
  });

  it("creates the conversation only when the first question is sent", async () => {
    vi.mocked(createAgentSession).mockResolvedValue(summary("s9"));
    vi.mocked(sendAgentMessage).mockResolvedValue({
      user_message: message("m1", "user", "Why Kafka?"),
      assistant_message: message("m2", "assistant", "It handled the volume [A1].", {
        citations: [citation("A1")],
        grounding: grounding(),
      }),
    });
    vi.mocked(getAgentSession).mockResolvedValue(
      session({
        id: "s9",
        messages: [
          message("m1", "user", "Why Kafka?"),
          message("m2", "assistant", "It handled the volume [A1].", {
            citations: [citation("A1")],
            grounding: grounding(),
          }),
        ],
      }),
    );
    await show();

    await userEvent.type(screen.getByRole("textbox", { name: "Your question" }), "Why Kafka?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/It handled the volume/)).toBeInTheDocument();
    expect(createAgentSession).toHaveBeenCalledWith({ profile_id: "p1" });
    expect(sendAgentMessage).toHaveBeenCalledWith("s9", "Why Kafka?");
    expect(screen.getByTestId("active")).toHaveTextContent("s9");
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Your question" })).toHaveValue("");
    });
  });

  it("keeps the question in the input when the first send fails", async () => {
    vi.mocked(createAgentSession).mockResolvedValue(summary("s9"));
    vi.mocked(sendAgentMessage).mockRejectedValue(new ApiError(502, "The AI provider failed."));
    await show();

    const box = screen.getByRole("textbox", { name: "Your question" });
    await userEvent.type(box, "Why Kafka?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The AI provider failed.");
    expect(box).toHaveValue("Why Kafka?");
    expect(screen.getByTestId("active")).toHaveTextContent("none");
  });

  it("shows an existing conversation in order and sends follow-ups to it", async () => {
    vi.mocked(getAgentSession).mockResolvedValue(
      session({
        id: "s1",
        messages: [
          message("m1", "user", "Tell me about yourself"),
          message("m2", "assistant", "I build data platforms [A1].", {
            citations: [citation("A1")],
            grounding: grounding(),
          }),
        ],
      }),
    );
    vi.mocked(sendAgentMessage).mockResolvedValue({
      user_message: message("m3", "user", "More detail?"),
      assistant_message: message("m4", "assistant", "Sure [A1].", {
        citations: [citation("A1")],
        grounding: grounding(),
      }),
    });
    await show("s1");

    expect(await screen.findByText("Tell me about yourself")).toBeInTheDocument();
    expect(screen.queryByText("Ask anything about your work, or try:")).not.toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "Your question" }), "More detail?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/Sure/)).toBeInTheDocument();
    expect(sendAgentMessage).toHaveBeenCalledWith("s1", "More detail?");
    expect(createAgentSession).not.toHaveBeenCalled();
  });

  it("offers to start a new chat when the conversation is gone", async () => {
    vi.mocked(getAgentSession).mockRejectedValue(new ApiError(404, "interview session not found"));
    await show("gone");

    expect(await screen.findByRole("alert")).toHaveTextContent("This conversation was not found.");
    await userEvent.click(screen.getByRole("button", { name: "Start a new chat" }));

    expect(screen.getByTestId("active")).toHaveTextContent("none");
  });

  it("offers a retry when the backend is unreachable", async () => {
    vi.mocked(getAgentSession).mockRejectedValue(new ApiError(0, "network error: down"));
    await show("s1");

    expect(await screen.findByRole("alert")).toHaveTextContent("network error: down");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
