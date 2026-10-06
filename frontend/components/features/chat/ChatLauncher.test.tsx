import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listAgentSessions, listProfiles } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ChatLauncher } from "./ChatLauncher";
import { ChatProvider } from "./ChatProvider";

let pathname = "/evidence";

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  listProfiles: vi.fn(),
  listAgentSessions: vi.fn(),
}));

function show() {
  return renderWithClient(
    <ChatProvider>
      <ChatLauncher />
    </ChatProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  window.localStorage.clear();
  pathname = "/evidence";
  vi.mocked(listProfiles).mockResolvedValue([]);
  vi.mocked(listAgentSessions).mockResolvedValue({ items: [], total: 0 });
});

describe("ChatLauncher", () => {
  it("opens the chat from the bubble and closes it again", async () => {
    show();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open chat" }));

    expect(screen.getByRole("dialog", { name: "Chat with your evidence" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close chat", expanded: true })).toBeInTheDocument();
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Close chat" }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the bubble", async () => {
    show();
    await userEvent.click(screen.getByRole("button", { name: "Open chat" }));

    await userEvent.type(screen.getByRole("textbox", { name: "Your question" }), "{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Open chat" })).toHaveFocus();
  });

  it.each(["/", "/get-started", "/chat"])("is not shown on %s", (route) => {
    pathname = route;
    show();

    expect(screen.queryByRole("button", { name: "Open chat" })).not.toBeInTheDocument();
  });

  it("remembers that it was open", async () => {
    const { unmount } = show();
    await userEvent.click(screen.getByRole("button", { name: "Open chat" }));
    unmount();

    show();

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("offers a link to the full page", async () => {
    show();
    await userEvent.click(screen.getByRole("button", { name: "Open chat" }));

    expect(screen.getByRole("link", { name: "Open full page" })).toHaveAttribute("href", "/chat");
  });
});
