import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, getResumeConflicts, getResumeDocument } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { resumeDocument } from "./fixtures";
import { ResumeDocumentPageClient } from "./ResumeDocumentPageClient";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getResumeDocument: vi.fn(),
  getResumeConflicts: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getResumeConflicts).mockResolvedValue({
    open: [],
    resolved: [],
    github_checked: false,
  });
});

describe("ResumeDocumentPageClient", () => {
  it("shows a loading state and then the document", async () => {
    vi.mocked(getResumeDocument).mockResolvedValue(resumeDocument());
    renderWithClient(<ResumeDocumentPageClient id="d1" />);

    expect(screen.getByRole("status", { name: "Loading resume" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Ada Lovelace — Engineer" }),
    ).toBeInTheDocument();
  });

  it("says a missing resume was not found, without a retry", async () => {
    vi.mocked(getResumeDocument).mockRejectedValue(new ApiError(404, "resume document not found"));
    renderWithClient(<ResumeDocumentPageClient id="nope" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("This resume was not found.");
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to your resumes" })).toHaveAttribute(
      "href",
      "/resume-builder",
    );
  });

  it("offers a retry when the backend is unreachable", async () => {
    vi.mocked(getResumeDocument).mockRejectedValue(new ApiError(0, "network error: down"));
    renderWithClient(<ResumeDocumentPageClient id="d1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("network error: down");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
