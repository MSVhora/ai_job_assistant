import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getResumeConflicts, resolveResumeConflict } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ConflictsPanel } from "./ConflictsPanel";
import { resumeDocument } from "./fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getResumeConflicts: vi.fn(),
  resolveResumeConflict: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("ConflictsPanel", () => {
  it("lists open conflicts with an edit-in-profile link and a keep-as-is action", async () => {
    vi.mocked(getResumeConflicts).mockResolvedValue({
      open: [
        {
          key: "c1",
          kind: "skill_without_evidence",
          severity: "warning",
          message: "Rust is listed but nothing you approved mentions it.",
          refs: {},
          suggested_actions: ["edit_profile", "keep_as_is"],
        },
      ],
      resolved: [],
      github_checked: false,
    });
    vi.mocked(resolveResumeConflict).mockResolvedValue(resumeDocument());
    renderWithClient(<ConflictsPanel documentId="d1" profileId="p1" version={3} />);

    expect(await screen.findByText(/Rust is listed/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit in profile" })).toHaveAttribute(
      "href",
      "/profile?profile=p1",
    );
    await userEvent.click(screen.getByRole("button", { name: "Keep as is" }));

    expect(resolveResumeConflict).toHaveBeenCalledWith("d1", "c1", "keep_as_is");
  });

  it("says when there is nothing to resolve", async () => {
    vi.mocked(getResumeConflicts).mockResolvedValue({
      open: [],
      resolved: [],
      github_checked: true,
    });
    renderWithClient(<ConflictsPanel documentId="d1" profileId="p1" version={3} />);

    expect(await screen.findByText("No open conflicts.")).toBeInTheDocument();
  });

  it("reports a failed check instead of staying silent", async () => {
    vi.mocked(getResumeConflicts).mockRejectedValue(new Error("backend unavailable"));
    renderWithClient(<ConflictsPanel documentId="d1" profileId="p1" version={3} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("backend unavailable");
  });
});
