import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  estimateEmployerMergeSuggestions,
  listEmployers,
  listGithubScopes,
  listOwners,
  listProfiles,
  mergeEmployers,
  suggestEmployerMerges,
  unmergeEmployer,
} from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { employerOption, PERSONAL_OPTION } from "../evidence/fixtures";
import { EmployersPanel } from "./EmployersPanel";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  addProfileExperience: vi.fn(),
  estimateEmployerMergeSuggestions: vi.fn(),
  listEmployers: vi.fn(),
  listGithubScopes: vi.fn(),
  listOwners: vi.fn(),
  listProfiles: vi.fn(),
  mergeEmployers: vi.fn(),
  suggestEmployerMerges: vi.fn(),
  unmergeEmployer: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const SAMSUNG = employerOption("Samsung");
const SRI = employerOption("Samsung Research Institute");
const ACME = employerOption("Acme Corp", {
  entries: 3,
  label: "Acme Corp · 2018 – 2024 · 3 roles",
});
const MERGED = employerOption("Wemsquare", {
  aliases: ["Wemsquare", "Wemsquare Technologies"],
  merged_from: ["Wemsquare Technologies"],
});

function estimate(overrides: Record<string, unknown> = {}) {
  return {
    prompt_tokens: 120,
    completion_tokens: 80,
    usd: 0.0004,
    basis: "configured_prices" as const,
    message: null,
    ...overrides,
  };
}

describe("EmployersPanel", () => {
  beforeEach(() => {
    for (const fn of [
      estimateEmployerMergeSuggestions,
      mergeEmployers,
      suggestEmployerMerges,
      unmergeEmployer,
    ]) {
      vi.mocked(fn).mockReset();
    }
    vi.mocked(listEmployers).mockResolvedValue([SAMSUNG, SRI, ACME, MERGED, PERSONAL_OPTION]);
    vi.mocked(listProfiles).mockResolvedValue([]);
    vi.mocked(listOwners).mockResolvedValue([]);
    vi.mocked(listGithubScopes).mockResolvedValue([]);
    vi.mocked(mergeEmployers).mockResolvedValue([]);
    vi.mocked(unmergeEmployer).mockResolvedValue([]);
  });

  it("lists one row per employer with its span and role count, and no personal row", async () => {
    renderWithClient(<EmployersPanel />);

    await screen.findByText("Acme Corp · 2018 – 2024 · 3 roles");
    const list = within(screen.getByRole("list", { name: "Employers" }));

    expect(list.getAllByRole("listitem")).toHaveLength(4);
    expect(list.getByText("Acme Corp · 2018 – 2024 · 3 roles")).toBeInTheDocument();
    expect(list.queryByText("Personal / open source")).not.toBeInTheDocument();
  });

  it("shows what was merged into an employer and lets you unmerge it", async () => {
    const user = userEvent.setup();
    renderWithClient(<EmployersPanel />);

    expect(await screen.findByText("Merged: Wemsquare Technologies")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Unmerge" }));

    await waitFor(() => {
      expect(unmergeEmployer).toHaveBeenCalledWith("wemsquare");
    });
  });

  it("merges the ticked employers under the chosen name", async () => {
    const user = userEvent.setup();
    renderWithClient(<EmployersPanel />);
    await user.click(await screen.findByRole("checkbox", { name: "Select Samsung to merge" }));
    expect(screen.queryByRole("button", { name: /Merge \d selected/ })).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("checkbox", { name: "Select Samsung Research Institute to merge" }),
    );

    await user.click(screen.getByRole("button", { name: "Merge 2 selected…" }));
    const dialog = await screen.findByRole("dialog", { name: "Merge employers" });
    await user.click(within(dialog).getByRole("radio", { name: "Samsung Research Institute" }));
    await user.click(within(dialog).getByRole("button", { name: "Merge" }));

    await waitFor(() => {
      expect(mergeEmployers).toHaveBeenCalledWith({
        canonical: "Samsung Research Institute",
        members: ["Samsung", "Samsung Research Institute"],
      });
    });
  });

  it("shows the cost first and only asks the model once you confirm", async () => {
    vi.mocked(estimateEmployerMergeSuggestions).mockResolvedValue(estimate());
    vi.mocked(suggestEmployerMerges).mockResolvedValue({
      suggestions: [],
      cost_usd: 0.0004,
      cached: false,
    });
    const user = userEvent.setup();
    renderWithClient(<EmployersPanel />);

    await user.click(await screen.findByRole("button", { name: "Suggest merges" }));

    expect(await screen.findByText(/≈ 200 tokens, ≈ \$0\.0004/)).toBeInTheDocument();
    expect(suggestEmployerMerges).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Ask the model" }));

    expect(
      await screen.findByText("No employers look like duplicates of each other."),
    ).toBeInTheDocument();
    expect(suggestEmployerMerges).toHaveBeenCalledTimes(1);
  });

  it("says when the answer is already known and costs nothing", async () => {
    vi.mocked(estimateEmployerMergeSuggestions).mockResolvedValue(
      estimate({ prompt_tokens: 0, completion_tokens: 0, usd: 0 }),
    );
    const user = userEvent.setup();
    renderWithClient(<EmployersPanel />);

    await user.click(await screen.findByRole("button", { name: "Suggest merges" }));

    expect(await screen.findByText(/no cost/)).toBeInTheDocument();
  });

  it("merges only the suggestions you leave ticked", async () => {
    vi.mocked(estimateEmployerMergeSuggestions).mockResolvedValue(estimate());
    vi.mocked(suggestEmployerMerges).mockResolvedValue({
      suggestions: [
        {
          canonical: "Samsung",
          members: ["Samsung", "Samsung Research Institute"],
          reason: "Same group.",
        },
        { canonical: "Acme Corp", members: ["Acme Corp", "Acme Labs"], reason: "" },
      ],
      cost_usd: 0.0004,
      cached: false,
    });
    const user = userEvent.setup();
    renderWithClient(<EmployersPanel />);
    await user.click(await screen.findByRole("button", { name: "Suggest merges" }));
    await user.click(await screen.findByRole("button", { name: "Ask the model" }));

    const list = within(await screen.findByRole("list", { name: "Suggested merges" }));
    expect(list.getByText("Same group.")).toBeInTheDocument();
    await user.click(list.getByRole("checkbox", { name: /Acme Corp \+ Acme Labs/ }));
    await user.click(screen.getByRole("button", { name: "Merge 1 selected" }));

    await waitFor(() => {
      expect(mergeEmployers).toHaveBeenCalledTimes(1);
    });
    expect(mergeEmployers).toHaveBeenCalledWith({
      canonical: "Samsung",
      members: ["Samsung", "Samsung Research Institute"],
    });
  });

  it("shows why suggesting failed", async () => {
    vi.mocked(estimateEmployerMergeSuggestions).mockRejectedValue(
      new Error("LLM provider is not configured"),
    );
    const user = userEvent.setup();
    renderWithClient(<EmployersPanel />);

    await user.click(await screen.findByRole("button", { name: "Suggest merges" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("not configured");
    expect(screen.getByRole("button", { name: "Ask the model" })).toBeDisabled();
  });

  it("needs two employers before suggesting and opens the add dialog", async () => {
    vi.mocked(listEmployers).mockResolvedValue([SAMSUNG, PERSONAL_OPTION]);
    const user = userEvent.setup();
    renderWithClient(<EmployersPanel />);

    await screen.findByRole("list", { name: "Employers" });
    expect(screen.getByRole("button", { name: "Suggest merges" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Add an employer" }));

    expect(await screen.findByRole("dialog", { name: "Add an employer" })).toBeInTheDocument();
  });

  it("says when there are no employers yet", async () => {
    vi.mocked(listEmployers).mockResolvedValue([PERSONAL_OPTION]);
    renderWithClient(<EmployersPanel />);

    expect(await screen.findByText(/No employers yet/)).toBeInTheDocument();
  });
});
