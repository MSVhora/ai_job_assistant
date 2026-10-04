import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  addResumeComment,
  applyResumeComments,
  generateResumePdf,
  getEvidenceItem,
  getResumeConflicts,
  includeRoleAnyway,
  pinResumeBullet,
  removeResumeBullet,
  writeAchievementBullet,
  type ResumeDocument,
} from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { DocumentView } from "./DocumentView";
import { resumeDocument } from "./fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  addResumeComment: vi.fn(),
  applyResumeComments: vi.fn(),
  generateResumePdf: vi.fn(),
  getEvidenceItem: vi.fn(),
  getResumeConflicts: vi.fn(),
  includeRoleAnyway: vi.fn(),
  pinResumeBullet: vi.fn(),
  removeResumeBullet: vi.fn(),
  writeAchievementBullet: vi.fn(),
}));

function show(document: ResumeDocument = resumeDocument()) {
  return renderWithClient(<DocumentView document={document} />);
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getResumeConflicts).mockResolvedValue({
    open: [],
    resolved: [],
    github_checked: false,
  });
  vi.mocked(getEvidenceItem).mockResolvedValue({
    id: "i1",
    kind: "pull_request",
    title: "Add the loader",
    url: "https://github.com/ada/engine/pull/7",
    is_private: true,
  } as never);
});

describe("review", () => {
  it("shows the written resume as text with private marks and evidence chips, and no PDF", async () => {
    show();

    expect(screen.getByText("Cut the nightly import from 42 to 9 minutes")).toBeInTheDocument();
    expect(screen.getByText("Private repo")).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: /pull request: Add the loader/ }),
    ).toHaveAttribute("href", "https://github.com/ada/engine/pull/7");
    expect(screen.queryByTitle("Resume PDF preview")).not.toBeInTheDocument();
    expect(generateResumePdf).not.toHaveBeenCalled();
    expect(screen.getByText("1 of 2 pages — 2 more achievements available.")).toBeInTheDocument();
  });

  it("only lists included bullets in the review and the rest under Not included", () => {
    show();

    const review = within(screen.getByRole("region", { name: "Resume content" }));
    expect(review.queryByText("Wrote the on-call runbook")).not.toBeInTheDocument();
    const notIncluded = within(screen.getByRole("list", { name: "Not included" }));
    expect(notIncluded.getByText("Wrote the on-call runbook")).toBeVisible();
    expect(notIncluded.getByText("Migrated billing")).toBeVisible();
  });

  it("warns that private marks are screen-only", () => {
    show();

    expect(screen.getByText(/marked on this screen only/)).toBeInTheDocument();
  });
});

describe("actions", () => {
  it("adds a not-included bullet by pinning it, and writes an unwritten one on demand", async () => {
    vi.mocked(pinResumeBullet).mockResolvedValue(resumeDocument());
    vi.mocked(writeAchievementBullet).mockResolvedValue(resumeDocument());
    show();

    const list = within(screen.getByRole("list", { name: "Not included" }));
    await userEvent.click(list.getByRole("button", { name: "Add" }));
    await userEvent.click(screen.getByRole("button", { name: "Write and add" }));

    expect(pinResumeBullet).toHaveBeenCalledWith("d1", "b2", true);
    expect(writeAchievementBullet).toHaveBeenCalledWith("d1", "a1");
  });

  it("removes an included bullet", async () => {
    vi.mocked(removeResumeBullet).mockResolvedValue(resumeDocument());
    show();

    await userEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(removeResumeBullet).toHaveBeenCalledWith("d1", "b1");
  });

  it("offers Include anyway for an omitted overlapping role", async () => {
    vi.mocked(includeRoleAnyway).mockResolvedValue(resumeDocument());
    const base = resumeDocument();
    show({
      ...base,
      generation: {
        ...base.generation,
        omitted_roles: [
          {
            block_id: "w0",
            company: "Old Co",
            title: "Dev",
            priority: 0.1,
            overlaps_with: "w1",
            reason: "Overlaps Engineer at Acme by more than 60 days and ranks lower.",
            position: 1,
            entry: {
              id: "w0",
              company: "Old Co",
              title: "Dev",
              start_date: "2019-01",
              end_date: "2020-06",
              is_current: false,
              highlights: [],
            },
          },
        ],
      },
    });

    expect(screen.getByText(/Omitted: Dev at Old Co/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Include anyway" }));

    expect(includeRoleAnyway).toHaveBeenCalledWith("d1", "w0");
  });
});

describe("comments", () => {
  it("adds a comment on a section and applies open comments", async () => {
    vi.mocked(addResumeComment).mockResolvedValue(resumeDocument());
    vi.mocked(applyResumeComments).mockResolvedValue(resumeDocument());
    const base = resumeDocument();
    show({
      ...base,
      comments: [
        {
          id: "c1",
          target: { section: "work", block_id: "w1" },
          text: "Emphasize the migration",
          status: "open",
          created_at: "2026-10-04T00:00:00Z",
        },
        {
          id: "c2",
          target: { section: "work", block_id: "w1" },
          text: "Add Kubernetes",
          status: "rejected",
          reason: "No evidence mentions Kubernetes.",
          action: "add_note",
          created_at: "2026-10-04T00:00:00Z",
        },
      ],
    });

    await userEvent.click(screen.getByRole("button", { name: "Comment on this section" }));
    await userEvent.type(screen.getByLabelText("Comment on this section"), "Shorten the summary");
    await userEvent.click(screen.getByRole("button", { name: "Add comment" }));
    expect(addResumeComment).toHaveBeenCalledWith("d1", {
      target: { section: "work", block_id: "w1" },
      text: "Shorten the summary",
    });

    expect(screen.getByText(/No evidence mentions Kubernetes/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add a note" })).toHaveAttribute("href", "/evidence");
    await userEvent.click(screen.getByRole("button", { name: "Apply 1 comment" }));
    expect(applyResumeComments).toHaveBeenCalledWith("d1");
  });
});

describe("pdf", () => {
  it("makes no PDF until asked, then previews it and flags it stale after a change", async () => {
    URL.createObjectURL = () => "blob:pdf-1";
    URL.revokeObjectURL = () => undefined;
    vi.mocked(generateResumePdf).mockResolvedValue(new Blob(["%PDF"], { type: "application/pdf" }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = (document: ResumeDocument) => (
      <QueryClientProvider client={client}>
        <DocumentView document={document} />
      </QueryClientProvider>
    );
    const { rerender } = render(view(resumeDocument()));

    await userEvent.click(screen.getByRole("button", { name: "Generate PDF" }));

    expect(await screen.findByTitle("Resume PDF preview")).toHaveAttribute("src", "blob:pdf-1");
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute("href", "blob:pdf-1");
    rerender(view(resumeDocument({ version: 4 })));
    expect(await screen.findByText(/generate it again/)).toBeInTheDocument();
  });

  it("shows why a PDF cannot be made", async () => {
    vi.mocked(generateResumePdf).mockRejectedValue(
      new Error("this resume cannot fit the chosen page count"),
    );
    show();

    await userEvent.click(screen.getByRole("button", { name: "Generate PDF" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("cannot fit");
  });
});
