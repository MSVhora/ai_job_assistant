import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnswerCard } from "./AnswerCard";
import { citation, grounding, message } from "./fixtures";

vi.mock("@/hooks/use-evidence-sources", () => ({
  useCreateNote: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

const onOpen = vi.fn();
const onReask = vi.fn();

function show(overrides: Parameters<typeof message>[3], busy = false) {
  render(
    <AnswerCard
      message={message("a1", "assistant", "I cut the import to 9 minutes [A1].", overrides)}
      question="Tell me about a time"
      busy={busy}
      onOpenCitation={onOpen}
      onReask={onReask}
    />,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("AnswerCard", () => {
  it("renders markers as chips that open the source", async () => {
    show({ citations: [citation("A1")], grounding: grounding() });

    expect(screen.getByText(/I cut the import to 9 minutes/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Source 1: Source A1" }));

    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ marker: "A1" }));
    expect(screen.getByText("Grounded")).toBeInTheDocument();
  });

  it("flags a partial answer with its gaps and what was left out", () => {
    show({
      citations: [citation("A1")],
      grounding: grounding({
        status: "partial",
        gaps: ["Part of the answer could not be confirmed from your evidence and was left out."],
        flagged_sentences: ["I also rewrote it in Rust [A1]."],
      }),
    });

    expect(screen.getByText("Partially grounded — see gaps")).toBeInTheDocument();
    expect(screen.getByText(/could not be confirmed from your evidence/)).toBeInTheDocument();
    expect(screen.getByText("I also rewrote it in Rust.")).toBeInTheDocument();
  });

  it("marks answers drawn from private repositories", () => {
    show({
      citations: [citation("A1", { private: true })],
      grounding: grounding({ used_private: true }),
    });

    expect(screen.getByText("Generated from private repository data")).toBeInTheDocument();
    expect(screen.getByText("Private repo")).toBeInTheDocument();
  });

  it("shows a Not in your evidence card with an Add a note action", async () => {
    show({ grounding: grounding({ status: "not_applicable", no_evidence: true }) });

    expect(screen.getByRole("heading", { name: "Not in your evidence" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Re-ask" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add a note" }));
    expect(screen.getByRole("dialog", { name: "Add a note" })).toBeInTheDocument();
  });

  it("offers to try again after a model failure", async () => {
    show({ grounding: grounding({ status: "refused", error: true }) });

    expect(screen.getByRole("alert")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onReask).toHaveBeenCalledWith("Tell me about a time");
  });

  it("copies the answer without markers", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    show({ citations: [citation("A1")], grounding: grounding() });

    await userEvent.click(screen.getByRole("button", { name: "Copy answer" }));

    expect(writeText).toHaveBeenCalledWith("I cut the import to 9 minutes.");
  });
});
