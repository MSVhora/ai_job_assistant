"use client";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  bulkApprove,
  getAchievement,
  getBulkEligible,
  getEvidenceItem,
  listAchievementsPage,
  listMergeProposals,
  listRevisions,
  mergeAchievements,
  runAchievementAction,
} from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { achievement, item, PENDING_METRIC } from "./fixtures";
import { ReviewPageClient } from "./ReviewPageClient";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  bulkApprove: vi.fn(),
  getAchievement: vi.fn(),
  getBulkEligible: vi.fn(),
  getEvidenceItem: vi.fn(),
  listAchievementsPage: vi.fn(),
  listMergeProposals: vi.fn(),
  listRevisions: vi.fn(),
  mergeAchievements: vi.fn(),
  runAchievementAction: vi.fn(),
}));

function page(items = [achievement()], total = items.length) {
  return Promise.resolve({ items, total });
}

describe("ReviewPageClient", () => {
  beforeEach(() => {
    for (const fn of [
      bulkApprove,
      getAchievement,
      getBulkEligible,
      getEvidenceItem,
      listAchievementsPage,
      listMergeProposals,
      listRevisions,
      mergeAchievements,
      runAchievementAction,
    ]) {
      vi.mocked(fn).mockReset();
    }
    vi.mocked(listAchievementsPage).mockImplementation(() => page());
    vi.mocked(listMergeProposals).mockResolvedValue([]);
    vi.mocked(listRevisions).mockResolvedValue([]);
    vi.mocked(getEvidenceItem).mockResolvedValue(item());
    vi.mocked(runAchievementAction).mockResolvedValue(achievement({ status: "approved" }));
  });

  it("starts on the Draft tab and shows each card's badges", async () => {
    vi.mocked(listAchievementsPage).mockImplementation(() =>
      page([
        achievement({
          derived_from_private: true,
          evidence_stale_at: "2026-10-02T00:00:00Z",
          metrics: [PENDING_METRIC],
          employer_ref: { company: "Acme Corp", start_date: "Mar 2021" },
        }),
      ]),
    );
    renderWithClient(<ReviewPageClient />);

    expect(
      await screen.findByRole("button", { name: "Faster nightly import" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Private repo")).toBeInTheDocument();
    expect(screen.getByText("Evidence updated — re-review")).toBeInTheDocument();
    expect(screen.getByText("1 to confirm")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp (Mar 2021)")).toBeInTheDocument();
    expect(screen.getByText("1 evidence item")).toBeInTheDocument();
    expect(listAchievementsPage).toHaveBeenCalledWith({ status: "draft", limit: 20, offset: 0 });
  });

  it("will not approve a draft that has unconfirmed metrics or no evidence", async () => {
    vi.mocked(listAchievementsPage).mockImplementation(() =>
      page([achievement({ metrics: [PENDING_METRIC], evidence: [] })]),
    );
    renderWithClient(<ReviewPageClient />);

    expect(await screen.findByRole("button", { name: "Approve" })).toBeDisabled();
    expect(
      screen.getByText("Link at least one piece of evidence; Confirm 1 metric"),
    ).toBeInTheDocument();
  });

  it("approves and rejects a clean draft from the list", async () => {
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);

    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() => {
      expect(runAchievementAction).toHaveBeenCalledWith("a1", "reject");
    });
    expect(runAchievementAction).toHaveBeenCalledWith("a1", "approve");
  });

  it.each([
    ["Approved", { status: "approved", limit: 20, offset: 0 }],
    ["Rejected", { status: "rejected", limit: 20, offset: 0 }],
    ["Needs attention", { status: "approved", stale: true, limit: 20, offset: 0 }],
  ])("the %s tab asks for the right list", async (label, expected) => {
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);
    await screen.findByRole("button", { name: "Faster nightly import" });

    await user.click(screen.getByRole("tab", { name: label }));

    await waitFor(() => {
      expect(listAchievementsPage).toHaveBeenLastCalledWith(expected);
    });
    expect(screen.getByRole("tab", { name: label })).toHaveAttribute("aria-selected", "true");
  });

  it("filters to private-derived achievements", async () => {
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);
    await screen.findByRole("button", { name: "Faster nightly import" });

    await user.click(screen.getByRole("checkbox", { name: "Private-derived only" }));

    await waitFor(() => {
      expect(listAchievementsPage).toHaveBeenLastCalledWith({
        status: "draft",
        limit: 20,
        offset: 0,
        private: true,
      });
    });
  });

  it("pages through long lists", async () => {
    vi.mocked(listAchievementsPage).mockImplementation(() => page([achievement()], 45));
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);

    await user.click(await screen.findByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(listAchievementsPage).toHaveBeenLastCalledWith({
        status: "draft",
        limit: 20,
        offset: 20,
      });
    });
    expect(await screen.findByText("21–40 of 45")).toBeInTheDocument();
  });

  it("explains an empty draft list and offers a retry on errors", async () => {
    vi.mocked(listAchievementsPage).mockImplementationOnce(() => Promise.reject(new Error("boom")));
    vi.mocked(listAchievementsPage).mockImplementation(() => page([], 0));
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);

    await user.click(await screen.findByRole("button", { name: "Retry" }));

    expect(await screen.findByText(/Run an extraction on the Evidence page/)).toBeInTheDocument();
  });

  it("merges two selected achievements and opens the result", async () => {
    vi.mocked(listAchievementsPage).mockImplementation(() =>
      page([
        achievement({ id: "a1", title: "Faster import" }),
        achievement({ id: "a2", title: "Import retry budget" }),
      ]),
    );
    vi.mocked(mergeAchievements).mockResolvedValue(
      achievement({ id: "m1", title: "Import hardening" }),
    );
    vi.mocked(getAchievement).mockResolvedValue(
      achievement({ id: "m1", title: "Import hardening" }),
    );
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);

    await user.click(
      await screen.findByRole("checkbox", { name: "Select Faster import for merging" }),
    );
    expect(screen.queryByRole("button", { name: /Merge \d selected/ })).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("checkbox", { name: "Select Import retry budget for merging" }),
    );
    await user.click(screen.getByRole("button", { name: "Merge 2 selected" }));

    const dialog = await screen.findByRole("dialog", { name: "Merge achievements" });
    await user.clear(within(dialog).getByLabelText("Title of the merged achievement"));
    await user.type(
      within(dialog).getByLabelText("Title of the merged achievement"),
      "Import hardening",
    );
    await user.click(within(dialog).getByRole("button", { name: "Merge" }));

    await waitFor(() => {
      expect(mergeAchievements).toHaveBeenCalledWith({
        ids: ["a1", "a2"],
        title: "Import hardening",
      });
    });
    expect(await screen.findByRole("dialog", { name: "Import hardening" })).toBeInTheDocument();
  });

  it("lists merge proposals and starts a merge from one", async () => {
    vi.mocked(listMergeProposals).mockResolvedValue([
      {
        first_id: "a1",
        first_title: "Faster import",
        second_id: "a2",
        second_title: "Import is faster",
        project_key: "ada/engine",
        similarity: 0.96,
      },
    ]);
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);

    await user.click(await screen.findByText("1 possible duplicate"));
    expect(screen.getByText(/96% similar/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Review merge" }));

    const dialog = await screen.findByRole("dialog", { name: "Merge achievements" });
    expect(within(dialog).getByText("Faster import")).toBeInTheDocument();
    expect(within(dialog).getByText("Import is faster")).toBeInTheDocument();
    expect(mergeAchievements).not.toHaveBeenCalled();
  });

  it("bulk approves the ticked, eligible drafts only", async () => {
    vi.mocked(getBulkEligible).mockResolvedValue({
      count: 2,
      items: [
        { id: "a1", title: "Clean one", evidence_count: 2 },
        { id: "a2", title: "Clean two", evidence_count: 1 },
      ],
    });
    vi.mocked(bulkApprove).mockResolvedValue({ approved: ["a2"], skipped: [] });
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);

    await user.click(await screen.findByRole("button", { name: "Approve all fully-evidenced…" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve all fully-evidenced" });
    expect(await within(dialog).findByText("Clean one")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Approve 2" })).toBeInTheDocument();

    await user.click(within(dialog).getByRole("checkbox", { name: /Clean one/ }));
    await user.click(within(dialog).getByRole("button", { name: "Approve 1" }));

    await waitFor(() => {
      expect(bulkApprove).toHaveBeenCalledWith(["a2"]);
    });
  });

  it("says when nothing qualifies for bulk approval", async () => {
    vi.mocked(getBulkEligible).mockResolvedValue({ count: 0, items: [] });
    const user = userEvent.setup();
    renderWithClient(<ReviewPageClient />);

    await user.click(await screen.findByRole("button", { name: "Approve all fully-evidenced…" }));

    expect(await screen.findByText(/No draft qualifies for bulk approval/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve 0" })).toBeDisabled();
  });
});
