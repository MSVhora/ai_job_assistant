"use client";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { addImpact, getImpactQueue, skipImpact } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { achievement } from "./fixtures";
import { ImpactQueueClient } from "./ImpactQueueClient";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  addImpact: vi.fn(),
  getImpactQueue: vi.fn(),
  skipImpact: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const FIRST = achievement({ id: "a1", title: "Faster nightly import" });
const SECOND = achievement({ id: "a2", title: "Cheaper storage tier" });

describe("ImpactQueueClient", () => {
  beforeEach(() => {
    vi.mocked(addImpact).mockReset().mockResolvedValue(FIRST);
    vi.mocked(skipImpact).mockReset().mockResolvedValue(FIRST);
    vi.mocked(getImpactQueue)
      .mockReset()
      .mockResolvedValue({ items: [FIRST, SECOND], total: 5 });
  });

  it("shows the best achievement first with its position and the overflow", async () => {
    renderWithClient(<ImpactQueueClient />);

    expect(await screen.findByRole("heading", { name: "Faster nightly import" })).toBeVisible();
    expect(screen.getByText("1 of 2")).toBeVisible();
    expect(screen.getByText("Showing the top 2 of 5 without a number.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save impact" })).toBeDisabled();
  });

  it("saves the number the user types", async () => {
    const user = userEvent.setup();
    renderWithClient(<ImpactQueueClient />);

    await user.type(await screen.findByLabelText("Measurable outcome"), "  9 minutes from 42  ");
    await user.click(screen.getByRole("button", { name: "Save impact" }));

    await waitFor(() => {
      expect(addImpact).toHaveBeenCalledWith("a1", "9 minutes from 42");
    });
  });

  it("records that there is no number to give", async () => {
    const user = userEvent.setup();
    renderWithClient(<ImpactQueueClient />);

    await user.click(await screen.findByRole("button", { name: "No number to give" }));

    await waitFor(() => {
      expect(skipImpact).toHaveBeenCalledWith("a1");
    });
  });

  it("moves to the next one on Not now without saving anything", async () => {
    const user = userEvent.setup();
    renderWithClient(<ImpactQueueClient />);

    await user.click(await screen.findByRole("button", { name: "Not now" }));

    expect(await screen.findByRole("heading", { name: "Cheaper storage tier" })).toBeVisible();
    expect(addImpact).not.toHaveBeenCalled();
    expect(skipImpact).not.toHaveBeenCalled();
  });

  it("says when nothing is left", async () => {
    vi.mocked(getImpactQueue).mockResolvedValue({ items: [], total: 0 });
    renderWithClient(<ImpactQueueClient />);

    expect(await screen.findByText(/Nothing left/)).toBeVisible();
  });
});
