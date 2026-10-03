"use client";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmMetric,
  editAchievement,
  getAchievement,
  getEvidenceItem,
  listRevisions,
  runAchievementAction,
  splitAchievement,
  unlinkEvidence,
  type Achievement,
} from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { AchievementDrawer } from "./AchievementDrawer";
import { achievement, item, PENDING_METRIC } from "./fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  confirmMetric: vi.fn(),
  editAchievement: vi.fn(),
  getAchievement: vi.fn(),
  getEvidenceItem: vi.fn(),
  listRevisions: vi.fn(),
  runAchievementAction: vi.fn(),
  splitAchievement: vi.fn(),
  unlinkEvidence: vi.fn(),
}));

const onClose = vi.fn();
const onOpen = vi.fn();

async function openDrawer(current: Achievement) {
  vi.mocked(getAchievement).mockResolvedValue(current);
  renderWithClient(
    <AchievementDrawer achievementId={current.id} onClose={onClose} onOpen={onOpen} />,
  );
  return await screen.findByRole("dialog", { name: current.title });
}

describe("AchievementDrawer", () => {
  beforeEach(() => {
    for (const fn of [
      confirmMetric,
      editAchievement,
      getAchievement,
      getEvidenceItem,
      listRevisions,
      runAchievementAction,
      splitAchievement,
      unlinkEvidence,
    ]) {
      vi.mocked(fn).mockReset();
    }
    onClose.mockReset();
    onOpen.mockReset();
    vi.mocked(getEvidenceItem).mockImplementation((id) =>
      Promise.resolve(item({ id, title: id === "i1" ? "Add the loader" : `Source ${id}` })),
    );
    vi.mocked(listRevisions).mockResolvedValue([]);
    vi.mocked(editAchievement).mockResolvedValue(achievement());
    vi.mocked(runAchievementAction).mockResolvedValue(achievement());
  });

  it("shows nothing while closed", () => {
    renderWithClient(<AchievementDrawer achievementId={null} onClose={onClose} onOpen={onOpen} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("loads the STAR story into an editor and saves changes", async () => {
    const user = userEvent.setup();
    await openDrawer(achievement());

    const result = screen.getByLabelText("Result");
    expect(screen.getByLabelText("Situation")).toHaveValue("The import took 42 minutes.");
    await user.clear(result);
    await user.type(result, "Down to 9 minutes");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(editAchievement).toHaveBeenCalledWith("a1", {
        title: "Faster nightly import",
        situation: "The import took 42 minutes.",
        task: "Reduce the runtime.",
        action: "Batched the writes.",
        result: "Down to 9 minutes",
      });
    });
  });

  it("sends a null result and explains why when the result is left empty", async () => {
    const user = userEvent.setup();
    await openDrawer(achievement({ result: null }));

    expect(screen.getByText(/No outcome is stated in the evidence/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(editAchievement).toHaveBeenCalledWith("a1", expect.objectContaining({ result: null }));
    });
  });

  it("saves skills, impact and difficulty", async () => {
    const user = userEvent.setup();
    await openDrawer(achievement());

    const skills = screen.getByLabelText("Skills");
    await user.clear(skills);
    await user.type(skills, "Go, Rust, Go");
    await user.selectOptions(screen.getByLabelText("Impact"), "reliability");
    await user.selectOptions(screen.getByLabelText("Difficulty"), "4");
    await user.click(screen.getByRole("button", { name: "Save tags" }));

    await waitFor(() => {
      expect(editAchievement).toHaveBeenCalledWith("a1", {
        skills: ["Go", "Rust"],
        difficulty: 4,
        impact_type: "reliability",
      });
    });
  });

  it("confirms a metric as written", async () => {
    vi.mocked(confirmMetric).mockResolvedValue(achievement());
    const user = userEvent.setup();
    await openDrawer(achievement({ metrics: [PENDING_METRIC] }));

    expect(screen.getByText("Needs your confirmation")).toBeInTheDocument();
    expect(screen.getByText(/Not found verbatim in the evidence/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm as written" }));

    await waitFor(() => {
      expect(confirmMetric).toHaveBeenCalledWith("a1", { index: 0, mode: "as_written" });
    });
  });

  it("lets you correct a metric's value before confirming it", async () => {
    vi.mocked(confirmMetric).mockResolvedValue(achievement());
    const user = userEvent.setup();
    await openDrawer(achievement({ metrics: [PENDING_METRIC] }));

    await user.click(screen.getByRole("button", { name: "Edit value" }));
    const value = screen.getByLabelText("Metric value");
    await user.clear(value);
    await user.type(value, "about 8x faster");
    await user.click(screen.getByRole("button", { name: "Confirm edited value" }));

    await waitFor(() => {
      expect(confirmMetric).toHaveBeenCalledWith("a1", {
        index: 0,
        mode: "edit",
        text: "about 8x faster",
      });
    });
  });

  it("shows verified metrics without confirmation buttons", async () => {
    await openDrawer(
      achievement({
        metrics: [
          { text: "42 to 9 minutes", source_quote: "from 42 to 9", verified: "evidence" },
          { text: "5 retries", verified: "user" },
        ],
      }),
    );

    expect(screen.getByText("Verified in the evidence")).toBeInTheDocument();
    expect(screen.getByText("Confirmed by you")).toBeInTheDocument();
    expect(screen.getByText(/Quoted: “from 42 to 9”/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm as written" })).not.toBeInTheDocument();
  });

  it("shows each evidence source with its link, text and quote", async () => {
    await openDrawer(achievement());

    const evidence = await screen.findByRole("list", { name: "Evidence" });
    expect(await within(evidence).findByRole("link", { name: "Add the loader" })).toHaveAttribute(
      "href",
      "https://github.com/ada/engine/pull/7",
    );
    expect(
      within(evidence).getByText("Cut the import from 42 minutes to 9 minutes."),
    ).toBeInTheDocument();
    expect(within(evidence).getByText(/Quote: “from 42 minutes to 9 minutes”/)).toBeInTheDocument();
    expect(within(evidence).getByText("primary")).toBeInTheDocument();
  });

  it("marks private sources", async () => {
    vi.mocked(getEvidenceItem).mockResolvedValue(item({ is_private: true }));

    await openDrawer(achievement());

    expect(await screen.findAllByText("Private repo")).not.toHaveLength(0);
  });

  it("warns when there is no evidence", async () => {
    await openDrawer(achievement({ evidence: [] }));

    expect(
      await screen.findByText(/no evidence yet, so it cannot be approved/),
    ).toBeInTheDocument();
  });

  it("unlinks a piece of evidence", async () => {
    vi.mocked(unlinkEvidence).mockResolvedValue(achievement());
    const user = userEvent.setup();
    await openDrawer(achievement());

    await user.click(await screen.findByRole("button", { name: "Unlink" }));

    await waitFor(() => {
      expect(unlinkEvidence).toHaveBeenCalledWith("a1", "i1");
    });
  });

  it("splits ticked evidence into a new achievement and opens it", async () => {
    vi.mocked(splitAchievement).mockResolvedValue(achievement({ id: "a2", title: "Loader fix" }));
    const user = userEvent.setup();
    await openDrawer(
      achievement({
        evidence: [
          { item_id: "i1", role: "primary", quote: null },
          { item_id: "i2", role: "supporting", quote: null },
        ],
      }),
    );

    const split = await screen.findByRole("button", { name: "Split 0 into a new achievement" });
    expect(split).toBeDisabled();
    await user.click(
      await screen.findByRole("checkbox", { name: "Move Source i2 to a new achievement" }),
    );
    await user.type(screen.getByLabelText("Title of the new achievement"), "Loader fix");
    await user.click(screen.getByRole("button", { name: "Split 1 into a new achievement" }));

    await waitFor(() => {
      expect(splitAchievement).toHaveBeenCalledWith("a1", {
        evidence_item_ids: ["i2"],
        title: "Loader fix",
      });
    });
    expect(onOpen).toHaveBeenCalledWith("a2");
  });

  it("does not offer a split when only one piece of evidence exists", async () => {
    await openDrawer(achievement());

    await screen.findByRole("list", { name: "Evidence" });
    expect(screen.queryByLabelText("Title of the new achievement")).not.toBeInTheDocument();
  });

  it("approves a clean draft and closes", async () => {
    const user = userEvent.setup();
    await openDrawer(achievement());

    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(runAchievementAction).toHaveBeenCalledWith("a1", "approve");
    });
    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("explains why a draft cannot be approved yet", async () => {
    await openDrawer(achievement({ metrics: [PENDING_METRIC] }));

    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Can't approve yet: Confirm 1 metric.");
  });

  it("offers unapprove and archive on approved rows, and re-review when evidence changed", async () => {
    vi.mocked(runAchievementAction).mockResolvedValue(achievement({ status: "approved" }));
    const user = userEvent.setup();
    await openDrawer(
      achievement({ status: "approved", evidence_stale_at: "2026-10-02T00:00:00Z" }),
    );

    expect(screen.getAllByText("Evidence updated — re-review")).not.toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "I re-reviewed the evidence" }));
    await waitFor(() => {
      expect(runAchievementAction).toHaveBeenCalledWith("a1", "acknowledge");
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Unapprove" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
  });

  it("restores a rejected achievement", async () => {
    const user = userEvent.setup();
    await openDrawer(achievement({ status: "rejected" }));

    await user.click(screen.getByRole("button", { name: "Restore to drafts" }));

    await waitFor(() => {
      expect(runAchievementAction).toHaveBeenCalledWith("a1", "restore");
    });
  });

  it("lists the revision history with readable diffs", async () => {
    vi.mocked(listRevisions).mockResolvedValue([
      {
        id: "r1",
        source: "manual_edit",
        diff: { difficulty: [3, 4] },
        created_at: "2026-10-03T10:00:00Z",
      },
      {
        id: "r2",
        source: "status_change",
        diff: { status: ["draft", "approved"], bulk: true },
        created_at: "2026-10-03T11:00:00Z",
      },
    ]);
    await openDrawer(achievement());

    const history = await screen.findByRole("list", { name: "Revision history" });
    expect(within(history).getByText("Edited")).toBeInTheDocument();
    expect(within(history).getByText("difficulty: 3 → 4")).toBeInTheDocument();
    expect(within(history).getByText('status: "draft" → "approved"')).toBeInTheDocument();
    expect(within(history).getByText("bulk: true")).toBeInTheDocument();
  });

  it("reports an achievement that cannot be loaded", async () => {
    vi.mocked(getAchievement).mockRejectedValue(new Error("gone"));
    renderWithClient(<AchievementDrawer achievementId="zz" onClose={onClose} onOpen={onOpen} />);

    expect(await screen.findByText("This achievement could not be loaded.")).toBeInTheDocument();
  });
});
