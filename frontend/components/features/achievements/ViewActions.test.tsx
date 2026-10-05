"use client";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { bulkApprove, bulkReject, type EmployerGroup } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ViewActions } from "./ViewActions";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  bulkApprove: vi.fn(),
  bulkReject: vi.fn(),
}));

const GROUPS: EmployerGroup[] = [
  {
    kind: "employer",
    label: "Acme",
    total: 3,
    eligible: 2,
    repositories: [
      {
        project_key: "acme/api",
        total: 2,
        eligible: 1,
        draft_ids: ["a1", "a2"],
        eligible_ids: ["a1"],
      },
      { project_key: "acme/web", total: 1, eligible: 1, draft_ids: ["a3"], eligible_ids: ["a3"] },
    ],
  },
];

describe("ViewActions", () => {
  beforeEach(() => {
    vi.mocked(bulkApprove).mockReset();
    vi.mocked(bulkReject).mockReset();
  });

  it("offers nothing until an employer or repository is chosen", () => {
    renderWithClient(<ViewActions groups={GROUPS} employer="" repository="" />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("approves the clean drafts of the chosen employer only after confirmation", async () => {
    vi.mocked(bulkApprove).mockResolvedValue({ approved: ["a1", "a3"], skipped: [] });
    renderWithClient(<ViewActions groups={GROUPS} employer="employer:Acme" repository="" />);

    await userEvent.click(screen.getByRole("button", { name: "Approve 2 clean" }));
    expect(bulkApprove).not.toHaveBeenCalled();
    await userEvent.click(await screen.findByRole("button", { name: "Approve 2" }));

    await waitFor(() => {
      expect(bulkApprove).toHaveBeenCalledWith(["a1", "a3"]);
    });
  });

  it("rejects every draft of the chosen repository after confirmation", async () => {
    vi.mocked(bulkReject).mockResolvedValue({ done: ["a1", "a2"], skipped: [] });
    renderWithClient(<ViewActions groups={GROUPS} employer="" repository="acme/api" />);

    await userEvent.click(screen.getByRole("button", { name: "Reject all 2" }));
    await userEvent.click(await screen.findByRole("button", { name: "Reject 2" }));

    await waitFor(() => {
      expect(bulkReject).toHaveBeenCalledWith(["a1", "a2"]);
    });
  });
});
