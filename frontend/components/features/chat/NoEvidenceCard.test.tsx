import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createNote, type EvidenceItem } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { NoEvidenceCard } from "./NoEvidenceCard";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  createNote: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(createNote).mockResolvedValue({ id: "n1" } as EvidenceItem);
});

describe("NoEvidenceCard", () => {
  it("saves a note prefilled with the question, then offers Re-ask", async () => {
    const onReask = vi.fn();
    renderWithClient(
      <NoEvidenceCard
        content="I can't find evidence for that."
        question="Why did you pick Kafka?"
        onReask={onReask}
        disabled={false}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Add a note" }));
    expect(screen.getByLabelText("Note title")).toHaveValue("Why did you pick Kafka?");
    await userEvent.type(screen.getByLabelText("What did you do?"), "Batch job could not keep up");
    await userEvent.click(screen.getByRole("button", { name: "Save note" }));

    expect(createNote).toHaveBeenCalledWith({
      title: "Why did you pick Kafka?",
      body: "Batch job could not keep up",
    });
    await userEvent.click(await screen.findByRole("button", { name: "Re-ask" }));
    expect(onReask).toHaveBeenCalledWith("Why did you pick Kafka?");
  });
});
