"use client";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listSyncs, startGithubSync } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { status, syncRun } from "./fixtures";
import { SyncPanel } from "./SyncPanel";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  listSyncs: vi.fn(),
  startGithubSync: vi.fn(),
}));

describe("SyncPanel", () => {
  beforeEach(() => {
    vi.mocked(listSyncs).mockReset();
    vi.mocked(startGithubSync).mockReset();
    vi.mocked(listSyncs).mockResolvedValue([]);
    vi.mocked(startGithubSync).mockResolvedValue({ sync_id: "s2", status: "pending" });
  });

  it("says when no sync has run yet", async () => {
    renderWithClient(<SyncPanel status={status()} />);

    expect(await screen.findByText("No sync has run yet.")).toBeInTheDocument();
  });

  it("starts an incremental refresh", async () => {
    const user = userEvent.setup();
    renderWithClient(<SyncPanel status={status()} />);

    await user.click(screen.getByRole("button", { name: "Sync now" }));

    await waitFor(() => {
      expect(startGithubSync).toHaveBeenCalledWith("incremental");
    });
  });

  it("explains a full re-sync and only starts it after confirmation", async () => {
    const user = userEvent.setup();
    renderWithClient(<SyncPanel status={status()} />);

    await user.click(screen.getByRole("button", { name: "Full re-sync" }));
    const dialog = await screen.findByRole("dialog", { name: "Run a full re-sync?" });
    expect(within(dialog).getByText(/approved achievements are never changed/)).toBeInTheDocument();
    expect(startGithubSync).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole("button", { name: "Start full re-sync" }));

    await waitFor(() => {
      expect(startGithubSync).toHaveBeenCalledWith("full");
    });
  });

  it("does not start anything when the full re-sync is cancelled", async () => {
    const user = userEvent.setup();
    renderWithClient(<SyncPanel status={status()} />);

    await user.click(screen.getByRole("button", { name: "Full re-sync" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(startGithubSync).not.toHaveBeenCalled();
  });

  it("disables syncing until a repository is enabled or a token exists", () => {
    const { unmount } = renderWithClient(<SyncPanel status={status({ scopes_enabled: 0 })} />);
    expect(screen.getByRole("button", { name: "Sync now" })).toBeDisabled();
    expect(screen.getByText(/Enable at least one repository first/)).toBeInTheDocument();
    unmount();

    renderWithClient(<SyncPanel status={status({ configured: false })} />);
    expect(screen.getByRole("button", { name: "Full re-sync" })).toBeDisabled();
  });

  it("disables the buttons while a run is active and shows its progress", async () => {
    vi.mocked(listSyncs).mockResolvedValue([
      syncRun({
        status: "running",
        progress: { items: 7, scopes: { "ada/engine": { status: "running", items: 7 } } },
        usage: { requests: 12 },
      }),
    ]);
    renderWithClient(<SyncPanel status={status()} />);

    expect(await screen.findByText("Syncing…")).toBeInTheDocument();
    expect(screen.getByText(/7 items · 12 GitHub requests used/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync now" })).toBeDisabled();
  });

  it("tells you when a run paused and when it resumes", async () => {
    vi.mocked(listSyncs).mockResolvedValue([
      syncRun({
        status: "paused",
        error: "the request budget for this run is used up",
        resume_at: "2030-01-01T12:30:00Z",
      }),
    ]);
    renderWithClient(<SyncPanel status={status()} />);

    expect(await screen.findByText("Sync paused")).toBeInTheDocument();
    const note = screen.getByRole("status");
    expect(note).toHaveTextContent("request budget for this run is used up");
    expect(note).toHaveTextContent(/Resumes at/);
    expect(screen.getByRole("button", { name: "Sync now" })).toBeEnabled();
  });

  it("surfaces warnings, chunk counts and re-review hints from a finished run", async () => {
    vi.mocked(listSyncs).mockResolvedValue([
      syncRun({
        progress: {
          items: 20,
          warnings: ["ada/old: GitHub returned 404"],
          chunks: { created: 5, embedded: 4, embed_failed: 1, pending_embedding: 1 },
          stale_flagged: 2,
        },
      }),
    ]);
    renderWithClient(<SyncPanel status={status()} />);

    expect(await screen.findByText("Sync finished")).toBeInTheDocument();
    expect(screen.getByText("ada/old: GitHub returned 404")).toBeInTheDocument();
    expect(screen.getByText(/Chunks: 5 new, 4 embedded, 1 waiting/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "re-review them" })).toHaveAttribute(
      "href",
      "/evidence/review",
    );
  });

  it("shows a failed run's error", async () => {
    vi.mocked(listSyncs).mockResolvedValue([
      syncRun({ status: "failed", error: "every repository failed" }),
    ]);
    renderWithClient(<SyncPanel status={status()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("every repository failed");
  });
});
