import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAchievement, type Achievement } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { CitationPanel } from "./CitationPanel";
import { citation } from "./fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAchievement: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("CitationPanel", () => {
  it("shows the achievement's STAR text, the quote and a link to the source", async () => {
    vi.mocked(getAchievement).mockResolvedValue({
      id: "a1",
      title: "Faster nightly import",
      situation: "Slow import",
      task: "Cut the runtime",
      action: "Batched the writes",
      result: "42 minutes to 9 minutes",
    } as unknown as Achievement);
    renderWithClient(
      <CitationPanel
        citation={citation("A1", {
          achievement_id: "a1",
          quote: "Cut the import from 42 to 9 minutes",
          url: "https://github.com/ada/engine/pull/7",
          private: true,
        })}
        onClose={vi.fn()}
      />,
    );

    expect(await screen.findByText("Batched the writes")).toBeInTheDocument();
    expect(screen.getByText("Cut the import from 42 to 9 minutes")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the source" })).toHaveAttribute(
      "href",
      "https://github.com/ada/engine/pull/7",
    );
    expect(screen.getByText("Generated from private repository data")).toBeInTheDocument();
  });

  it("renders nothing when no source is selected", () => {
    renderWithClient(<CitationPanel citation={null} onClose={vi.fn()} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
