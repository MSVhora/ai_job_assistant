import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createResumeDocument, listMatchesPage, type MatchResponse } from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ResumeCreateForm } from "./ResumeCreateForm";
import { resumeDocument } from "./fixtures";

const push = vi.fn<(href: string) => void>();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  createResumeDocument: vi.fn(),
  listMatchesPage: vi.fn(),
}));

const profile = (id: string, name: string) => ({
  profile_id: id,
  name,
  source_resume_filename: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
});
const profiles = [profile("p1", "Backend track"), profile("p2", "Data track")];

function match(id: string, title: string, rationale: string): MatchResponse {
  return {
    id,
    final_score: 0.8,
    rationale,
    job_posting: { title, company: "Globex" },
  } as unknown as MatchResponse;
}

function show(matchId: string | null = null) {
  return renderWithClient(
    <ResumeCreateForm profiles={profiles} initialProfileId="p1" initialMatchId={matchId} />,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(createResumeDocument).mockResolvedValue(resumeDocument({ id: "d9" }));
});

describe("ResumeCreateForm", () => {
  it("creates a resume with the chosen length and template and opens it for review", async () => {
    show();

    await userEvent.selectOptions(screen.getByLabelText("Length"), "2");
    await userEvent.selectOptions(screen.getByLabelText("Template"), "compact");
    await userEvent.click(screen.getByRole("button", { name: "Create resume" }));

    expect(createResumeDocument).toHaveBeenCalledWith({
      profile_id: "p1",
      page_target: 2,
      template: "compact",
      exclude_private: false,
    });
    await vi.waitFor(() => {
      expect(push).toHaveBeenCalledWith("/resume-builder/d9");
    });
  });

  it("offers the tailoring strength only once a job description is in play", async () => {
    show();
    expect(screen.queryByText("Tailoring strength")).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Paste one"));

    expect(screen.getByText("Tailoring strength")).toBeInTheDocument();
    expect(screen.getByLabelText(/Balanced/)).toBeChecked();
    expect(
      screen.getByText(/Work that doesn.t match the JD is still included/),
    ).toBeInTheDocument();
  });

  it("sends a pasted job description with the chosen strength and blocks an empty paste", async () => {
    show();
    await userEvent.click(screen.getByLabelText("Paste one"));

    await userEvent.click(screen.getByRole("button", { name: "Create resume" }));
    expect(await screen.findByText(/Paste the job description/)).toBeInTheDocument();
    expect(createResumeDocument).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("Job description"), "We run Snowflake");
    await userEvent.click(screen.getByLabelText("Strong"));
    await userEvent.click(screen.getByRole("button", { name: "Create resume" }));

    expect(createResumeDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        job_description: "We run Snowflake",
        tailoring_strength: "strong",
      }),
    );
  });

  it("starts on the match tab when arriving from a match and shows why it matched", async () => {
    vi.mocked(listMatchesPage).mockResolvedValue({
      items: [match("m1", "Staff Engineer", "Strong Python overlap")],
      total: 1,
    });
    show("m1");

    expect(await screen.findByText(/Strong Python overlap/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Create resume" }));

    expect(createResumeDocument).toHaveBeenCalledWith(
      expect.objectContaining({ match_id: "m1", tailoring_strength: "balanced" }),
    );
  });

  it("shows the backend error and keeps the form usable", async () => {
    vi.mocked(createResumeDocument).mockRejectedValue(new Error("rate limited by the provider"));
    show();

    await userEvent.click(screen.getByRole("button", { name: "Create resume" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("rate limited by the provider");
    expect(screen.getByRole("button", { name: "Create resume" })).toBeEnabled();
  });
});
