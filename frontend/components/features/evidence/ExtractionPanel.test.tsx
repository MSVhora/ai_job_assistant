"use client";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  estimateExtraction,
  getChunkSummary,
  getExtractionRun,
  startExtraction,
  type ExtractionEstimate,
} from "@/lib/api";

import { renderWithClient } from "../test-utils";
import { ExtractionPanel } from "./ExtractionPanel";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  estimateExtraction: vi.fn(),
  getChunkSummary: vi.fn(),
  getExtractionRun: vi.fn(),
  startExtraction: vi.fn(),
}));

function estimate(overrides: Partial<ExtractionEstimate> = {}): ExtractionEstimate {
  return {
    estimate_id: "e".repeat(64),
    chunks_total: 10,
    chunks_up_to_date: 4,
    chunks_cached: 1,
    chunks_to_extract: 5,
    llm_cost: {
      prompt_tokens: 4000,
      completion_tokens: 2000,
      usd: 0.0123,
      basis: "litellm_price_map",
    },
    embedding_cost: {
      prompt_tokens: 1200,
      completion_tokens: 0,
      usd: 0.0004,
      basis: "litellm_price_map",
    },
    total_usd: 0.0127,
    private_chunks: 0,
    private_share: 0,
    ...overrides,
  };
}

describe("ExtractionPanel", () => {
  beforeEach(() => {
    vi.mocked(estimateExtraction).mockReset();
    vi.mocked(getChunkSummary).mockReset();
    vi.mocked(getExtractionRun).mockReset();
    vi.mocked(startExtraction).mockReset();
    vi.mocked(getChunkSummary).mockResolvedValue({
      chunks: 10,
      tokens: 5000,
      private_chunks: 3,
      private_share: 0.3,
      embedded: 9,
      pending_embedding: 1,
      by_kind: {},
    });
  });

  it("summarizes the evidence chunks including the private share", async () => {
    renderWithClient(<ExtractionPanel />);

    expect(
      await screen.findByText(/10 evidence chunks \(5,000 tokens\), 9 embedded, 1 waiting/),
    ).toBeInTheDocument();
    expect(screen.getByText(/30% come from private repositories/)).toBeInTheDocument();
  });

  it("disables the estimate when there are no chunks yet", async () => {
    vi.mocked(getChunkSummary).mockResolvedValue({
      chunks: 0,
      tokens: 0,
      private_chunks: 0,
      private_share: 0,
      embedded: 0,
      pending_embedding: 0,
      by_kind: {},
    });
    renderWithClient(<ExtractionPanel />);

    await screen.findByText(/0 evidence chunks/);
    expect(screen.getByRole("button", { name: "Estimate extraction" })).toBeDisabled();
  });

  it("shows the estimate before anything is sent and starts only on confirm", async () => {
    vi.mocked(estimateExtraction).mockResolvedValue(estimate());
    vi.mocked(startExtraction).mockResolvedValue({ run_id: "run-1", status: "pending" });
    vi.mocked(getExtractionRun).mockResolvedValue({
      id: "run-1",
      status: "running",
      estimate: {},
      progress: { total: 5, done: 2 },
      usage: {},
      error: null,
      created_at: "2026-10-03T10:00:00Z",
      updated_at: "2026-10-03T10:00:00Z",
    });
    const user = userEvent.setup();
    renderWithClient(<ExtractionPanel />);
    await screen.findByText(/10 evidence chunks/);

    await user.click(screen.getByRole("button", { name: "Estimate extraction" }));

    const dialog = await screen.findByRole("dialog", { name: "Extract achievements?" });
    expect(
      within(dialog).getByText(/5 chunks will be sent to your LLM provider/),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/1 are already cached/)).toBeInTheDocument();
    expect(within(dialog).getByText(/6,000 tokens/)).toBeInTheDocument();
    expect(within(dialog).queryByRole("note")).not.toBeInTheDocument();
    expect(startExtraction).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole("button", { name: "Extract achievements" }));

    await waitFor(() => {
      expect(startExtraction).toHaveBeenCalledWith("e".repeat(64));
    });
    expect(await screen.findByText("Extracting… 2 of 5 chunks")).toBeInTheDocument();
  });

  it("repeats the private-chunk count as the second checkpoint", async () => {
    vi.mocked(estimateExtraction).mockResolvedValue(
      estimate({ private_chunks: 2, private_share: 0.4 }),
    );
    const user = userEvent.setup();
    renderWithClient(<ExtractionPanel />);
    await screen.findByText(/10 evidence chunks/);

    await user.click(screen.getByRole("button", { name: "Estimate extraction" }));

    expect(await screen.findByRole("note")).toHaveTextContent(
      "2 of 6 chunks (40%) come from private repositories",
    );
  });

  it("says cost is unavailable instead of guessing", async () => {
    vi.mocked(estimateExtraction).mockResolvedValue(
      estimate({
        llm_cost: {
          prompt_tokens: 100,
          completion_tokens: 50,
          usd: null,
          basis: "unavailable",
          message: "cost unavailable for this model",
        },
        total_usd: null,
      }),
    );
    const user = userEvent.setup();
    renderWithClient(<ExtractionPanel />);
    await screen.findByText(/10 evidence chunks/);

    await user.click(screen.getByRole("button", { name: "Estimate extraction" }));

    expect(
      await screen.findByText(/cost unavailable for this model for extraction/),
    ).toBeInTheDocument();
  });

  it("blocks confirming when there is nothing to extract", async () => {
    vi.mocked(estimateExtraction).mockResolvedValue(
      estimate({ chunks_to_extract: 0, chunks_cached: 0 }),
    );
    const user = userEvent.setup();
    renderWithClient(<ExtractionPanel />);
    await screen.findByText(/10 evidence chunks/);

    await user.click(screen.getByRole("button", { name: "Estimate extraction" }));

    expect(await screen.findByText("There is nothing new to extract.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Extract achievements" })).toBeDisabled();
  });

  it("links to the review page when a run finished with drafts", async () => {
    vi.mocked(estimateExtraction).mockResolvedValue(estimate());
    vi.mocked(startExtraction).mockResolvedValue({ run_id: "run-1", status: "pending" });
    vi.mocked(getExtractionRun).mockResolvedValue({
      id: "run-1",
      status: "succeeded",
      estimate: {},
      progress: { total: 5, done: 5, achievements: 4, rejected: 1, failed: 0 },
      usage: { cost_usd: 0.01 },
      error: null,
      created_at: "2026-10-03T10:00:00Z",
      updated_at: "2026-10-03T10:00:00Z",
    });
    const user = userEvent.setup();
    renderWithClient(<ExtractionPanel />);
    await screen.findByText(/10 evidence chunks/);

    await user.click(screen.getByRole("button", { name: "Estimate extraction" }));
    await user.click(await screen.findByRole("button", { name: "Extract achievements" }));

    expect(await screen.findByText("Extraction finished")).toBeInTheDocument();
    expect(screen.getByText(/4 drafts created, 1 rejected by validation/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review the drafts" })).toHaveAttribute(
      "href",
      "/evidence/review",
    );
  });
});
