"use client";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { archiveOlderVersion, getOlderVersion } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { RetireOlderPanel } from "./RetireOlderPanel";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  archiveOlderVersion: vi.fn(),
  getOlderVersion: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const PREVIEW = {
  prompt_version: "achievement_v2",
  would_archive: 7,
  kept_edited: 2,
  kept_not_reextracted: 3,
};

describe("RetireOlderPanel", () => {
  beforeEach(() => {
    vi.mocked(getOlderVersion).mockReset().mockResolvedValue(PREVIEW);
    vi.mocked(archiveOlderVersion).mockReset().mockResolvedValue({ archived: 7 });
  });

  it("stays hidden when nothing older can be replaced", async () => {
    vi.mocked(getOlderVersion).mockResolvedValue({ ...PREVIEW, would_archive: 0 });
    renderWithClient(<RetireOlderPanel />);

    await waitFor(() => {
      expect(getOlderVersion).toHaveBeenCalled();
    });
    expect(screen.queryByRole("region", { name: "Replace older extractions" })).toBeNull();
  });

  it("explains what is kept and archives only after confirmation", async () => {
    const user = userEvent.setup();
    renderWithClient(<RetireOlderPanel />);

    expect(await screen.findByText(/2 you edited are always kept/)).toBeVisible();
    expect(screen.getByText(/3 whose source was not re-extracted are kept/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Archive 7 older…" }));
    expect(archiveOlderVersion).not.toHaveBeenCalled();
    await user.click(await screen.findByRole("button", { name: "Archive 7" }));

    await waitFor(() => {
      expect(archiveOlderVersion).toHaveBeenCalledTimes(1);
    });
  });
});
