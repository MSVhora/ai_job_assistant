"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getSetupCheck, type SetupCheck } from "@/lib/api";

import { TaskModels } from "./TaskModels";

vi.mock("@/lib/api", () => ({ getSetupCheck: vi.fn() }));

function setupCheck(taskModels: Record<string, string>): SetupCheck {
  return {
    llm_configured: true,
    embedding_configured: true,
    adzuna_configured: true,
    apify_configured: false,
    github_token_configured: false,
    task_models: taskModels,
    warnings: [],
  };
}

function renderModels() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TaskModels />
    </QueryClientProvider>,
  );
}

describe("TaskModels", () => {
  beforeEach(() => {
    vi.mocked(getSetupCheck).mockReset();
  });

  it("lists the routed model for each task", async () => {
    vi.mocked(getSetupCheck).mockResolvedValue(
      setupCheck({ extract: "gemini/flash", write: "gemini/pro" }),
    );
    renderModels();

    expect(await screen.findByRole("heading", { name: "Models per task" })).toBeInTheDocument();
    expect(screen.getByText("Extract")).toBeInTheDocument();
    expect(screen.getByText("gemini/flash")).toBeInTheDocument();
    expect(screen.getByText("Write")).toBeInTheDocument();
    expect(screen.getByText("gemini/pro")).toBeInTheDocument();
  });

  it("renders nothing while loading or when no task models are reported", async () => {
    vi.mocked(getSetupCheck).mockResolvedValue(setupCheck({}));
    renderModels();

    expect(screen.queryByRole("heading", { name: "Models per task" })).not.toBeInTheDocument();
    await vi.waitFor(() => {
      expect(getSetupCheck).toHaveBeenCalled();
    });
    expect(screen.queryByRole("heading", { name: "Models per task" })).not.toBeInTheDocument();
  });
});
